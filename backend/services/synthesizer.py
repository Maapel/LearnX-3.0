"""
synthesizer.py — LearnX 3.0 Backend
Two synthesis functions:
  - synthesize_outline(): fast skeleton generation (~3-5s)
  - synthesize_lesson(): deep JIT lesson generation with exercises

LLM cascade: Gemini Flash (structured output) → Groq → Ollama → static fallback
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path)

from google import genai
from google.genai import types as genai_types
from groq import Groq
import httpx

logger = logging.getLogger(__name__)

_GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
_GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
_OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.2")

_llm_semaphore = asyncio.Semaphore(1)

_GEMINI_MODELS = ["models/gemini-2.0-flash-lite", "models/gemini-2.0-flash"]
_GROQ_MODEL    = "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# Gemini structured output schemas
# ---------------------------------------------------------------------------

_OUTLINE_SCHEMA = genai_types.Schema(
    type=genai_types.Type.OBJECT,
    properties={
        "course_title": genai_types.Schema(type=genai_types.Type.STRING),
        "difficulty_level": genai_types.Schema(
            type=genai_types.Type.STRING,
            enum=["Beginner", "Intermediate", "Advanced"],
        ),
        "estimated_hours": genai_types.Schema(type=genai_types.Type.NUMBER),
        "modules": genai_types.Schema(
            type=genai_types.Type.ARRAY,
            items=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "module_title": genai_types.Schema(type=genai_types.Type.STRING),
                    "lessons": genai_types.Schema(
                        type=genai_types.Type.ARRAY,
                        items=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                "lesson_id": genai_types.Schema(type=genai_types.Type.STRING),
                                "lesson_title": genai_types.Schema(type=genai_types.Type.STRING),
                                "lesson_context": genai_types.Schema(type=genai_types.Type.STRING),
                                "target_search_queries": genai_types.Schema(
                                    type=genai_types.Type.ARRAY,
                                    items=genai_types.Schema(type=genai_types.Type.STRING),
                                ),
                            },
                        ),
                    ),
                },
            ),
        ),
    },
)

_LESSON_SCHEMA = genai_types.Schema(
    type=genai_types.Type.OBJECT,
    properties={
        "lesson_id": genai_types.Schema(type=genai_types.Type.STRING),
        "lesson_title": genai_types.Schema(type=genai_types.Type.STRING),
        "video_url": genai_types.Schema(type=genai_types.Type.STRING),
        "sections": genai_types.Schema(
            type=genai_types.Type.ARRAY,
            items=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "section_title": genai_types.Schema(type=genai_types.Type.STRING),
                    "explanation": genai_types.Schema(type=genai_types.Type.STRING),
                    "code_snippet": genai_types.Schema(type=genai_types.Type.STRING),
                    "visual_analogy": genai_types.Schema(type=genai_types.Type.STRING),
                },
            ),
        ),
        "exercises": genai_types.Schema(
            type=genai_types.Type.ARRAY,
            items=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "question": genai_types.Schema(type=genai_types.Type.STRING),
                    "options": genai_types.Schema(
                        type=genai_types.Type.ARRAY,
                        items=genai_types.Schema(type=genai_types.Type.STRING),
                    ),
                    "correct_answer": genai_types.Schema(type=genai_types.Type.STRING),
                    "explanation": genai_types.Schema(type=genai_types.Type.STRING),
                },
            ),
        ),
        "key_takeaways": genai_types.Schema(
            type=genai_types.Type.ARRAY,
            items=genai_types.Schema(type=genai_types.Type.STRING),
        ),
    },
)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

_VALID_ESCAPES = set('"\\/bfnrtu')


def _fix_invalid_escapes(text: str) -> str:
    """Replace invalid JSON backslash sequences (e.g. \\p, \\s) with the bare character."""
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char in _VALID_ESCAPES:
                result.append(text[i])
                result.append(next_char)
                i += 2
            else:
                result.append(next_char)
                i += 2
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _escape_control_chars_in_strings(text: str) -> str:
    """
    Walk the JSON character-by-character. When inside a JSON string value,
    replace raw control characters (newline, carriage-return, tab, and others)
    with their proper JSON escape sequences instead of stripping them entirely.
    This fixes the "Invalid control character" error caused by LLMs that emit
    literal newlines inside multi-line string values.
    """
    result: list[str] = []
    in_string = False
    escaped = False
    _ESC_MAP = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}

    for ch in text:
        if escaped:
            result.append(ch)
            escaped = False
        elif ch == '\\':
            result.append(ch)
            escaped = True
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string and ch in _ESC_MAP:
            result.append(_ESC_MAP[ch])
        elif in_string and ord(ch) < 0x20:
            # Any other unescaped control char inside a string → drop it
            pass
        else:
            result.append(ch)

    return "".join(result)


def _fix_python_literals(text: str) -> str:
    """Replace Python literals that are invalid JSON: None→null, True→true, False→false."""
    # Only replace when they appear as JSON values (after : or [ or ,)
    text = re.sub(r'(?<=[:\[,\s])\bNone\b', 'null', text)
    text = re.sub(r'(?<=[:\[,\s])\bTrue\b', 'true', text)
    text = re.sub(r'(?<=[:\[,\s])\bFalse\b', 'false', text)
    return text


def _fix_missing_values(text: str) -> str:
    """Replace bare empty values like `"key": ,` or `"key": }` with null."""
    text = re.sub(r':\s*,', ': null,', text)
    text = re.sub(r':\s*}', ': null}', text)
    text = re.sub(r':\s*]', ': null]', text)
    return text


def _safe_json_loads(text: str) -> dict:
    """
    Parse JSON robustly through 7 escalating strategies:
    1. Standard parse (handles clean LLM output)
    2. Extract first {...} block (strips preamble text)
    3. Escape raw control chars inside strings (fixes literal newlines in values)
    4. Fix Python literals (None/True/False → null/true/false)
    5. Fix missing/empty values ("key": , → "key": null,)
    6. Fix invalid backslash escapes (fixes \\p, \\s etc.)
    7. All fixes combined + strip remaining junk
    """
    # 1. Standard
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")

    snippet = text[start:end + 1]

    # 2. Raw snippet
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        pass

    # 3. Escape control chars inside strings (fixes literal newlines from Groq)
    try:
        return json.loads(_escape_control_chars_in_strings(snippet))
    except json.JSONDecodeError:
        pass

    # 4. Python literals (None/True/False)
    try:
        return json.loads(_fix_python_literals(snippet))
    except json.JSONDecodeError:
        pass

    # 5. Missing/empty values
    try:
        return json.loads(_fix_missing_values(_fix_python_literals(snippet)))
    except json.JSONDecodeError:
        pass

    # 6. Fix invalid backslash sequences
    try:
        return json.loads(_fix_invalid_escapes(snippet))
    except json.JSONDecodeError:
        pass

    # 7. All fixes combined + strip remaining control chars
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', snippet)
    fixed = _fix_missing_values(_fix_python_literals(_fix_invalid_escapes(_escape_control_chars_in_strings(cleaned))))
    return json.loads(fixed)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = []
        skip = True
        for line in lines:
            if skip and line.startswith("```"):
                skip = False
                continue
            if line.strip() == "```" and not skip:
                break
            inner.append(line)
        text = "\n".join(inner).strip()
    return text


# ---------------------------------------------------------------------------
# LLM call helpers
# ---------------------------------------------------------------------------

def _gemini_call(prompt: str, schema: genai_types.Schema) -> str:
    if not _GEMINI_API_KEY:
        raise RuntimeError("No GEMINI_API_KEY")
    client = genai.Client(api_key=_GEMINI_API_KEY)
    last_exc: Exception | None = None
    for model_name in _GEMINI_MODELS:
        try:
            logger.info("Gemini %s → structured output", model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return response.text
        except Exception as exc:
            logger.warning("Gemini %s failed: %s", model_name, exc)
            last_exc = exc
    raise RuntimeError(f"All Gemini models failed: {last_exc}")


def _groq_call(system_prompt: str, user_prompt: str, max_retries: int = 3, max_tokens: int = 8192) -> str:
    if not _GROQ_API_KEY:
        raise RuntimeError("No GROQ_API_KEY")
    client = Groq(api_key=_GROQ_API_KEY)
    delays = [5, 15, 45]
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as exc:
            err = str(exc)
            is_rate = "429" in err or "rate_limit" in err.lower()
            if is_rate and attempt < max_retries - 1:
                time.sleep(delays[attempt])
            else:
                raise


def _ollama_call(system_prompt: str, user_prompt: str) -> str:
    url = f"{_OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": _OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.7},
    }
    with httpx.Client(timeout=300.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"]


def _llm_cascade(prompt: str, schema: genai_types.Schema, groq_system: str) -> str | None:
    """Try Gemini → Groq → Ollama. Returns raw text or None."""
    # Gemini
    try:
        return _gemini_call(prompt, schema)
    except Exception as e:
        logger.warning("Gemini failed: %s — trying Groq", e)
    # Groq
    try:
        return _groq_call(groq_system, prompt)
    except Exception as e:
        logger.warning("Groq failed: %s — trying Ollama", e)
    # Ollama
    try:
        return _ollama_call(groq_system, prompt)
    except Exception as e:
        logger.error("Ollama also failed: %s", e)
    return None


# ---------------------------------------------------------------------------
# synthesize_outline — fast skeleton, no content
# ---------------------------------------------------------------------------

_OUTLINE_GROQ_SYSTEM = (
    "You are a Master Curriculum Designer. Return ONLY valid JSON. "
    "You must group the course into 3 to 5 distinct logical Modules "
    "(e.g. 'Module 1: The Basics', 'Module 2: Core Mechanics', 'Module 3: Advanced Patterns'). "
    "Do NOT generate a flat list. Every module must clearly build on the previous one, "
    "forming a coherent learning progression from foundation to mastery. "
    "Use real UUID4 strings for lesson_id fields. "
    "For each lesson write a lesson_context (1-2 sentences: exactly what this lesson covers "
    "and how it flows from the previous lesson) and target_search_queries (1-2 highly specific "
    "search queries a librarian expert would use to find precisely the right content for that "
    "lesson — not generic, not broad)."
)

_OUTLINE_PROMPT_TMPL = """You are a Master Curriculum Designer creating a structured course outline.
You act as both an expert teacher and a search strategist.

CRITICAL STRUCTURE RULE:
- Group all lessons into 3 to 5 distinct logical Modules.
- Module titles must reflect a clear learning progression, e.g.:
    Module 1: Foundations & Setup
    Module 2: Core Mechanics
    Module 3: Intermediate Patterns
    Module 4: Advanced Techniques
    Module 5: Real-World Projects
- Do NOT create a flat list of topics. Each module must build directly on the previous one.

Course topic: {topic}
Difficulty: {difficulty}

For EVERY lesson you must provide:
1. lesson_id — a real UUID4 string
2. lesson_title — concise and descriptive
3. lesson_context — 1-2 sentences: what exactly this lesson covers + how it connects to the previous lesson. This is injected into the AI content generator to prevent drift.
4. target_search_queries — 1-2 highly specific search queries. What exact phrase returns the perfect resource for THIS lesson? E.g. for "useEffect cleanup": ["React useEffect cleanup function return tutorial", "prevent memory leaks useEffect React hooks"]

Return this exact JSON structure:
{{
  "course_title": "string",
  "difficulty_level": "{difficulty}",
  "estimated_hours": <number>,
  "modules": [
    {{
      "module_title": "Module N: <descriptive title>",
      "lessons": [
        {{
          "lesson_id": "<uuid4>",
          "lesson_title": "string",
          "lesson_context": "string",
          "target_search_queries": ["query1", "query2"]
        }}
      ]
    }}
  ]
}}

Create 3-5 modules with 2-4 lessons each. Return ONLY JSON."""


async def synthesize_outline(topic: str, difficulty: str) -> dict:
    prompt = _OUTLINE_PROMPT_TMPL.format(topic=topic, difficulty=difficulty)

    async with _llm_semaphore:
        raw = await asyncio.to_thread(_llm_cascade, prompt, _OUTLINE_SCHEMA, _OUTLINE_GROQ_SYSTEM)

    if raw:
        try:
            data = _safe_json_loads(_strip_fences(raw))
            # Ensure all lessons have UUIDs and required new fields
            for mod in data.get("modules", []):
                for lesson in mod.get("lessons", []):
                    if not lesson.get("lesson_id"):
                        lesson["lesson_id"] = str(uuid.uuid4())
                    if not lesson.get("lesson_context"):
                        lesson["lesson_context"] = f"This lesson covers {lesson.get('lesson_title', topic)} in the context of {topic}."
                    if not lesson.get("target_search_queries"):
                        lesson["target_search_queries"] = [
                            f"{lesson.get('lesson_title', topic)} tutorial",
                            f"{lesson.get('lesson_title', topic)} {difficulty} guide",
                        ]
            return data
        except Exception as e:
            logger.error("Outline parse failed: %s", e)

    # Fallback outline
    def _fallback_lesson(title: str) -> dict:
        return {
            "lesson_id": str(uuid.uuid4()),
            "lesson_title": title,
            "lesson_context": f"This lesson covers {title} as part of learning {topic}.",
            "target_search_queries": [f"{title} tutorial", f"{title} {difficulty} explained"],
        }

    return {
        "course_title": f"Introduction to {topic}",
        "difficulty_level": difficulty,
        "estimated_hours": 2.0,
        "modules": [
            {
                "module_title": f"Getting Started with {topic}",
                "lessons": [
                    _fallback_lesson(f"What is {topic}?"),
                    _fallback_lesson(f"Core Concepts of {topic}"),
                    _fallback_lesson(f"Practical {topic} Examples"),
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# synthesize_lesson — deep JIT generation with exercises
# ---------------------------------------------------------------------------

_LESSON_GROQ_SYSTEM = (
    "You are an expert educator writing a deep, structured lesson. Return ONLY valid JSON. "
    "You will receive a lesson_context — treat it as your strict scope. "
    "Write 3-5 sections, each with a specific title, detailed explanation (1-3 paragraphs with "
    "markdown formatting: **bold** key terms, bullet lists), an optional code_snippet (fenced "
    "code block), and an optional visual_analogy (one sentence). "
    "Do NOT write a single monolithic text block. Chunk the content into clearly titled sections. "
    "exercises must have correct_answer that EXACTLY matches one of the options strings. "
    "video_url must be null if you are not certain of a real YouTube URL."
)

_LESSON_PROMPT_TMPL = """You are generating a deep, structured lesson for an online course.

STRICT SCOPE — you must ONLY cover what this context specifies:
\"\"\"{lesson_context}\"\"\"
Ignore any scraped material that does not directly support this scope.

Lesson: {lesson_title}
Course: {course_title}
Difficulty: {difficulty}

Source material (use only what is relevant to the scope above):
{context}

Return a JSON object with this EXACT structure:
{{
  "lesson_id": "{lesson_id}",
  "lesson_title": "{lesson_title}",
  "video_url": "<real youtube URL or null>",
  "sections": [
    {{
      "section_title": "<specific heading, not generic>",
      "explanation": "<1-3 paragraphs with **bold** key terms and bullet points. Be thorough.>",
      "code_snippet": "<fenced code block with language tag, or null>",
      "visual_analogy": "<one sentence real-world analogy, or null>"
    }}
  ],
  "exercises": [
    {{
      "question": "string",
      "options": ["option A", "option B", "option C", "option D"],
      "correct_answer": "<must exactly match one of the options strings above>",
      "explanation": "1-2 sentences why this answer is correct"
    }}
  ],
  "key_takeaways": ["string", ...]
}}

RULES — violating any rule makes the output invalid:
1. sections: generate 3-5 sections covering different aspects of the lesson scope
2. Each section explanation: 1-3 paragraphs, use **bold** for key terms, use bullet lists where appropriate — NO single-sentence explanations
3. code_snippet: must use fenced markdown code blocks with a language tag (```python, ```js etc). Null if not applicable.
4. visual_analogy: one sentence only. Real-world comparison. Null if forced.
5. exercises: 2-3 MCQ questions, each with 3-4 options
6. correct_answer must be the EXACT string of one of the options (copy-paste it)
7. video_url: only a confirmed real YouTube URL for this exact topic, otherwise null
Return ONLY JSON, no explanation."""


async def synthesize_lesson(
    lesson_id: str,
    lesson_title: str,
    lesson_context: str,
    course_title: str,
    difficulty: str,
    search_results: list[dict],
    scraped_articles: list[dict],
    transcripts: list[dict],
) -> dict:
    # Build context from sourced material
    parts: list[str] = []
    for r in search_results[:3]:
        parts.append(f"[Search] {r.get('title', '')} — {r.get('snippet', '')[:300]}")
    for a in scraped_articles[:3]:
        parts.append(f"[Article] {a.get('title', '')}\n{a.get('content', '')[:2000]}")
    for t in transcripts[:2]:
        parts.append(f"[Transcript] {t.get('transcript', '')[:1000]}")
    context = "\n\n".join(parts) if parts else "No source material. Use your knowledge."

    prompt = _LESSON_PROMPT_TMPL.format(
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        lesson_context=lesson_context,
        course_title=course_title,
        difficulty=difficulty,
        context=context,
    )

    async with _llm_semaphore:
        raw = await asyncio.to_thread(_llm_cascade, prompt, _LESSON_SCHEMA, _LESSON_GROQ_SYSTEM)

    if raw:
        try:
            data = _safe_json_loads(_strip_fences(raw))
            data["lesson_id"] = lesson_id  # enforce correct ID
            # Validate correct_answer matches an option
            for ex in data.get("exercises", []):
                if ex.get("correct_answer") not in ex.get("options", []):
                    opts = ex.get("options", [])
                    ex["correct_answer"] = opts[0] if opts else ex["correct_answer"]
            # Remove LLM-hallucinated time — router calculates it programmatically
            data.pop("estimated_time_minutes", None)
            return data
        except Exception as e:
            logger.error("Lesson parse failed: %s\nRaw (first 500 chars): %s", e, (raw or "")[:500])

    # Fallback lesson
    return {
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "video_url": None,
        "sections": [
            {
                "section_title": f"Introduction to {lesson_title}",
                "explanation": (
                    f"**{lesson_title}** is a fundamental concept in {course_title}.\n\n"
                    "This lesson covers the core ideas you need to understand before moving forward. "
                    "All AI synthesis providers failed — please check your API keys and retry.\n\n"
                    "Key areas this lesson would cover:\n"
                    f"- The definition and purpose of {lesson_title}\n"
                    "- How it fits into the broader course structure\n"
                    "- Common use cases and practical applications"
                ),
                "code_snippet": None,
                "visual_analogy": None,
            }
        ],
        "exercises": [
            {
                "question": f"What is the primary purpose of {lesson_title}?",
                "options": ["To learn theory", "To apply concepts", "Both theory and practice", "Neither"],
                "correct_answer": "Both theory and practice",
                "explanation": "Effective learning combines theoretical understanding with practical application.",
            }
        ],
        "key_takeaways": [
            f"Understanding {lesson_title} is essential to mastering {course_title}.",
            "Check your API keys and retry for AI-generated content.",
        ],
    }
