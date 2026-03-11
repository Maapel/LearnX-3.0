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
        "estimated_time_minutes": genai_types.Schema(type=genai_types.Type.INTEGER),
        "video_url": genai_types.Schema(type=genai_types.Type.STRING),
        "concept_summary": genai_types.Schema(type=genai_types.Type.STRING),
        "practical_example": genai_types.Schema(type=genai_types.Type.STRING),
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


def _safe_json_loads(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start:end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass
        try:
            return json.loads(_fix_invalid_escapes(snippet))
        except json.JSONDecodeError:
            pass
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', snippet)
        return json.loads(_fix_invalid_escapes(cleaned))
    raise ValueError("No JSON object found in response")


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


def _groq_call(system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
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
                max_tokens=4096,
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
    "You are a curriculum designer. Return ONLY valid JSON. "
    "Generate a course outline with 3-5 modules, each with 2-4 lessons. "
    "Use real UUID strings for lesson_id fields."
)

_OUTLINE_PROMPT_TMPL = """Design a structured course outline for: {topic}
Difficulty: {difficulty}

Return a JSON object with this exact structure:
{{
  "course_title": "string",
  "difficulty_level": "{difficulty}",
  "estimated_hours": <number>,
  "modules": [
    {{
      "module_title": "string",
      "lessons": [
        {{"lesson_id": "<uuid>", "lesson_title": "string"}},
        ...
      ]
    }},
    ...
  ]
}}

Use real UUID4 strings for lesson_id. Create 3-5 modules with 2-4 lessons each.
Return ONLY JSON, no explanation."""


async def synthesize_outline(topic: str, difficulty: str) -> dict:
    prompt = _OUTLINE_PROMPT_TMPL.format(topic=topic, difficulty=difficulty)

    async with _llm_semaphore:
        raw = await asyncio.to_thread(_llm_cascade, prompt, _OUTLINE_SCHEMA, _OUTLINE_GROQ_SYSTEM)

    if raw:
        try:
            data = _safe_json_loads(_strip_fences(raw))
            # Ensure all lessons have valid UUIDs
            for mod in data.get("modules", []):
                for lesson in mod.get("lessons", []):
                    if not lesson.get("lesson_id"):
                        lesson["lesson_id"] = str(uuid.uuid4())
            return data
        except Exception as e:
            logger.error("Outline parse failed: %s", e)

    # Fallback outline
    return {
        "course_title": f"Introduction to {topic}",
        "difficulty_level": difficulty,
        "estimated_hours": 2.0,
        "modules": [
            {
                "module_title": f"Getting Started with {topic}",
                "lessons": [
                    {"lesson_id": str(uuid.uuid4()), "lesson_title": f"What is {topic}?"},
                    {"lesson_id": str(uuid.uuid4()), "lesson_title": f"Core Concepts of {topic}"},
                    {"lesson_id": str(uuid.uuid4()), "lesson_title": f"Practical {topic} Examples"},
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# synthesize_lesson — deep JIT generation with exercises
# ---------------------------------------------------------------------------

_LESSON_GROQ_SYSTEM = (
    "You are an expert educator. Return ONLY valid JSON. "
    "concept_summary must be STRICTLY 3-4 sentences — no long paragraphs. "
    "exercises must have correct_answer that EXACTLY matches one of the options strings. "
    "video_url must be null if you are not certain of a real YouTube URL."
)

_LESSON_PROMPT_TMPL = """Generate a detailed interactive lesson for:

Lesson: {lesson_title}
Course: {course_title}
Difficulty: {difficulty}

Source material to reference:
{context}

Return a JSON object with this EXACT structure:
{{
  "lesson_id": "{lesson_id}",
  "lesson_title": "{lesson_title}",
  "estimated_time_minutes": <integer>,
  "video_url": "<youtube URL or null>",
  "concept_summary": "<STRICTLY 3-4 punchy sentences. No long text. Core idea only.>",
  "practical_example": "<markdown code block or real-world example, or null>",
  "exercises": [
    {{
      "question": "string",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "<must exactly match one option>",
      "explanation": "1-2 sentences why this is correct"
    }}
  ],
  "key_takeaways": ["string", ...]
}}

Rules:
- concept_summary: EXACTLY 3-4 sentences, punchy, beginner-friendly
- exercises: generate 2-3 MCQ questions with 3-4 options each
- correct_answer must be the EXACT string of one of the options
- video_url: only a real known YouTube URL, otherwise null
- practical_example: use fenced code blocks for code, null if N/A
Return ONLY JSON."""


async def synthesize_lesson(
    lesson_id: str,
    lesson_title: str,
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
            return data
        except Exception as e:
            logger.error("Lesson parse failed: %s", e)

    # Fallback lesson
    return {
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "estimated_time_minutes": 10,
        "video_url": None,
        "concept_summary": (
            f"{lesson_title} is a key topic in {course_title}. "
            "This lesson covers the fundamental concepts you need to understand. "
            "Study the source material carefully to build a solid foundation. "
            "Practice regularly to reinforce your understanding."
        ),
        "practical_example": None,
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
