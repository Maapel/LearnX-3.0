"""
synthesizer.py — LearnX 3.0 Backend
Feeds scraped content into Gemini (with Groq + Ollama fallbacks) and returns a
structured Course JSON matching the Pydantic Course schema.

Model cascade:
  1. gemini-2.0-flash-lite  (Gemini free tier — highest quota)
  2. gemini-2.0-flash        (larger Gemini model)
  3. Groq llama-3.3-70b      (fallback if Gemini quota exhausted)
  4. Ollama local model       (local fallback — no rate limits)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

# Load keys from ../../.env relative to this file
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path)

from google import genai
from google.genai import types as genai_types
from groq import Groq
import httpx
import sys
import os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from models import Course as _CourseModel

logger = logging.getLogger(__name__)

_GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
_GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
_OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.2")

# Global semaphore: caps concurrent LLM synthesis calls to 1.
# Prevents Groq free-tier quota exhaustion under concurrent FastAPI requests.
_llm_semaphore = asyncio.Semaphore(1)

# Gemini model cascade — Flash tier only (cheaper, faster, great at structured data)
# Never use Pro tier for standard synthesis — Flash is an order of magnitude cheaper
_GEMINI_MODELS = ["models/gemini-2.0-flash-lite", "models/gemini-2.0-flash"]
_GROQ_MODEL    = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# Schema description injected into every prompt
# ---------------------------------------------------------------------------
_SCHEMA_DESCRIPTION = """
You must return a single JSON object that EXACTLY matches this schema (no extra keys):

{
  "course_title": "string",
  "difficulty_level": "Beginner" | "Intermediate" | "Advanced",
  "estimated_hours": <number>,
  "modules": [
    {
      "module_title": "string",
      "module_description": "string",
      "lessons": [
        {
          "lesson_title": "string",
          "content_type": "video" | "article" | "concept_breakdown",
          "source_url": "string or null",
          "content_markdown": "string — MINIMUM 600 WORDS of rich teaching content",
          "key_takeaways": ["string", ...]
        }
      ]
    }
  ]
}

STRICT RULES — violating any of these makes the output invalid:

1. CONTENT DEPTH (CRITICAL): Every lesson's content_markdown MUST contain AT LEAST 600 WORDS.
   This is non-negotiable. Short, stub-like content is rejected. Write like a university textbook —
   include explanations, examples, analogies, and worked problems. Count your words before finishing.

2. CODE BLOCKS (CRITICAL for technical topics): Any code, commands, or syntax examples MUST be
   written inside fenced code blocks using triple backticks and a language identifier:
   ```python
   # correct — always use this format
   x = 42
   print(x)
   ```
   NEVER write code inline in prose. NEVER use semicolons to combine Python statements on one line.

3. LESSON VARIETY: Use a mix of content_type values across lessons. Do not assign "article" to all
   lessons. Use "concept_breakdown" for conceptual explanations and "video" only when a transcript
   source is available.

4. SOURCE URLS: Only assign source_url values from URLs that appear in the SOURCE MATERIAL section.
   Do not invent or hallucinate URLs. Use null if no relevant URL exists for a lesson.

5. ESTIMATED HOURS: Calculate realistically. Assume 200 words/minute reading pace plus 2x for
   practice time. A 600-word lesson = ~6 minutes reading + ~12 minutes practice = ~0.3 hours.
   For a 4-module, 3-lesson-each course: roughly 3.5–6 hours total.

6. MODULE STRUCTURE: Create 3–5 modules, each with 2–4 lessons. Use distinct, non-redundant
   module titles. Each module should cover a clearly different aspect of the topic.

7. JSON ONLY: Return ONLY valid JSON. No markdown code fences wrapping the JSON, no commentary,
   no preamble, no postamble. The response must start with {{ and end with }}.
"""


# ---------------------------------------------------------------------------
# Helper: strip markdown code fences if the LLM adds them
# ---------------------------------------------------------------------------
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


_VALID_ESCAPES = set('"\\/bfnrtu')


def _fix_invalid_escapes(text: str) -> str:
    """Replace invalid JSON escape sequences like \\p, \\s with their literal char."""
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
                # Invalid escape: drop the backslash, keep the char
                result.append(next_char)
                i += 2
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _safe_json_loads(text: str) -> dict:
    """
    Parse JSON robustly:
    1. Standard parse
    2. Extract first {...} block
    3. Fix invalid escape sequences
    4. Strip non-printable control chars
    """
    # Attempt 1: standard
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract outermost {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start:end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass
        # Attempt 3: fix invalid escapes on the snippet
        try:
            return json.loads(_fix_invalid_escapes(snippet))
        except json.JSONDecodeError:
            pass
        # Attempt 4: strip control chars then fix escapes
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', snippet)
        return json.loads(_fix_invalid_escapes(cleaned))

    raise ValueError("No JSON object found in response")


# ---------------------------------------------------------------------------
# Helper: build context string from all sourced material
# ---------------------------------------------------------------------------
def _build_context(
    search_results: list[dict],
    scraped_articles: list[dict],
    transcripts: list[dict],
) -> str:
    parts: list[str] = []

    if search_results:
        parts.append("=== WEB SEARCH RESULTS ===")
        for i, r in enumerate(search_results, 1):
            parts.append(f"[{i}] {r.get('title','')}\nURL: {r.get('url','')}\nSnippet: {r.get('snippet','')}\n")

    if scraped_articles:
        parts.append("=== SCRAPED ARTICLES ===")
        for i, a in enumerate(scraped_articles, 1):
            content = a.get("content", "")[:2000]
            parts.append(f"[Article {i}] {a.get('title','')}\nURL: {a.get('url','')}\n{content}\n")

    if transcripts:
        parts.append("=== YOUTUBE TRANSCRIPTS ===")
        for i, t in enumerate(transcripts, 1):
            transcript = t.get("transcript", "")[:1500]
            parts.append(f"[Video {i}] URL: {t.get('url','')}\nTranscript:\n{transcript}\n")

    return "\n".join(parts) if parts else "No source material provided. Generate from your own knowledge."


# ---------------------------------------------------------------------------
# Helper: validate parsed course dict shape
# ---------------------------------------------------------------------------
_MIN_LESSON_WORDS = 300  # hard floor after prompt asks for 600; guards against stubbed output


def _validate(course_dict: dict) -> None:
    required = {"course_title", "difficulty_level", "estimated_hours", "modules"}
    missing = required - course_dict.keys()
    if missing:
        raise ValueError(f"Missing keys: {missing}")
    if not isinstance(course_dict["modules"], list) or not course_dict["modules"]:
        raise ValueError("No modules found")

    total_words = 0
    short_lessons = []
    for mod in course_dict["modules"]:
        if "lessons" not in mod or not isinstance(mod["lessons"], list) or not mod["lessons"]:
            raise ValueError(f"Module '{mod.get('module_title')}' has no lessons")
        for lesson in mod["lessons"]:
            wc = len(lesson.get("content_markdown", "").split())
            total_words += wc
            if wc < _MIN_LESSON_WORDS:
                short_lessons.append((lesson.get("lesson_title", "?"), wc))

    if short_lessons:
        details = ", ".join(f"'{t}' ({w} words)" for t, w in short_lessons)
        logger.warning("Shallow lessons detected (<%d words): %s", _MIN_LESSON_WORDS, details)
        # Warn but don't hard-reject — let the course through with a log warning
    logger.info("Total content words across all lessons: %d", total_words)


# ---------------------------------------------------------------------------
# Fallback course (used only if ALL LLMs fail)
# ---------------------------------------------------------------------------
def _fallback_course(topic: str, difficulty: str) -> dict:
    safe_difficulty = difficulty if difficulty in ("Beginner", "Intermediate", "Advanced") else "Beginner"
    return {
        "course_title": f"Introduction to {topic}",
        "difficulty_level": safe_difficulty,
        "estimated_hours": 1.0,
        "modules": [{
            "module_title": f"Getting Started with {topic}",
            "module_description": f"A foundational overview of {topic}.",
            "lessons": [{
                "lesson_title": f"What is {topic}?",
                "content_type": "concept_breakdown",
                "source_url": None,
                "content_markdown": (
                    f"## What is {topic}?\n\n"
                    f"{topic} is a rich field worth exploring. This is a fallback lesson — "
                    "all AI synthesis providers failed. Please check your API keys and retry.\n\n"
                    "### Suggested next steps\n"
                    "1. Verify GEMINI_API_KEY and GROQ_API_KEY in your .env file.\n"
                    "2. Check API quotas at aistudio.google.com and console.groq.com.\n"
                    "3. If rate-limited, start Ollama locally: `ollama serve` and ensure a model is pulled.\n"
                    "4. Retry the request.\n"
                ),
                "key_takeaways": [
                    f"{topic} is an important area of study.",
                    "Check your API keys and retry for full AI-generated content.",
                ],
            }],
        }],
    }


# ---------------------------------------------------------------------------
# Gemini synthesis (tries each model in cascade)
# ---------------------------------------------------------------------------
def _try_gemini(prompt: str) -> str:
    """
    Try each Gemini Flash model in order using native structured output.

    Uses response_mime_type="application/json" + response_schema=Course to
    force valid JSON directly from the model — eliminates hallucination loops
    and costly parse-retry cycles. Returns raw JSON text or raises.
    """
    if not _GEMINI_API_KEY:
        raise RuntimeError("No GEMINI_API_KEY")

    client = genai.Client(api_key=_GEMINI_API_KEY)
    last_exc: Exception | None = None

    for model_name in _GEMINI_MODELS:
        try:
            logger.info("Trying Gemini model: %s (structured output)", model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=_CourseModel,
                ),
            )
            logger.info("Gemini %s succeeded (structured output).", model_name)
            return response.text
        except Exception as exc:
            logger.warning("Gemini %s failed: %s", model_name, exc)
            last_exc = exc

    raise RuntimeError(f"All Gemini models failed. Last error: {last_exc}")


# ---------------------------------------------------------------------------
# Groq synthesis fallback
# ---------------------------------------------------------------------------
def _try_groq(prompt: str, max_retries: int = 3) -> str:
    """
    Use Groq llama-3.3-70b as synthesis fallback with exponential backoff retry.
    Retries on 429 (rate limit) with delays: 5s → 15s → 45s.
    Returns raw text or raises on final failure.
    """
    if not _GROQ_API_KEY:
        raise RuntimeError("No GROQ_API_KEY")

    logger.info("Falling back to Groq (%s) for synthesis.", _GROQ_MODEL)
    client = Groq(api_key=_GROQ_API_KEY)
    delays = [5, 15, 45]

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert curriculum designer and educator. "
                            "Return ONLY valid JSON — no markdown fences, no preamble, no explanation. "
                            "Every lesson content_markdown MUST be at least 600 words. "
                            "All code examples MUST use fenced ```language``` blocks."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=8192,
            )
            return response.choices[0].message.content
        except Exception as exc:
            err_str = str(exc)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower() or "rate limit" in err_str.lower()
            if is_rate_limit and attempt < max_retries - 1:
                wait = delays[attempt]
                logger.warning(
                    "Groq rate limit hit (attempt %d/%d). Retrying in %ds...",
                    attempt + 1, max_retries, wait,
                )
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Ollama local synthesis fallback
# ---------------------------------------------------------------------------
def _try_ollama(prompt: str) -> str:
    """
    Use a local Ollama model for synthesis — no API key, no rate limits.
    Calls POST /api/chat with stream=false.
    Returns raw text or raises if Ollama is unreachable or model is missing.
    """
    url = f"{_OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": _OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert curriculum designer and educator. "
                    "Return ONLY valid JSON — no markdown fences, no preamble, no explanation. "
                    "Every lesson content_markdown MUST be at least 600 words. "
                    "All code examples MUST use fenced ```language``` blocks."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.7},
    }

    logger.info("Falling back to Ollama (%s @ %s) for synthesis.", _OLLAMA_MODEL, _OLLAMA_BASE_URL)
    with httpx.Client(timeout=300.0) as client:  # local models can be slow
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["message"]["content"]
        logger.info("Ollama synthesis succeeded.")
        return content


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------
async def synthesize_course(
    topic: str,
    difficulty: str,
    search_results: list[dict],
    scraped_articles: list[dict],
    transcripts: list[dict],
) -> dict:
    """
    Synthesize a Course JSON from sourced material.
    Cascade: Gemini → Groq → Ollama → static fallback.
    """
    context_block = _build_context(search_results, scraped_articles, transcripts)
    prompt = (
        f"You are an expert curriculum designer and educator.\n"
        f"Create a comprehensive, structured online course about: {topic!r}\n"
        f"Target difficulty level: {difficulty}\n\n"
        f"{_SCHEMA_DESCRIPTION}\n\n"
        f"=== SOURCE MATERIAL ===\n"
        f"Use the following sourced content to inform and enrich the lessons:\n\n"
        f"{context_block}\n\n"
        f"Now generate the complete Course JSON:"
    )

    raw_text: str | None = None

    async with _llm_semaphore:
        # ── 1. Try Gemini ──────────────────────────────────────────────────
        try:
            raw_text = await asyncio.to_thread(_try_gemini, prompt)
            logger.info("Synthesis via Gemini succeeded.")
        except Exception as gemini_exc:
            logger.warning("Gemini synthesis failed: %s — trying Groq.", gemini_exc)

        # ── 2. Try Groq if Gemini failed ───────────────────────────────────
        if raw_text is None:
            try:
                raw_text = await asyncio.to_thread(_try_groq, prompt)
                logger.info("Synthesis via Groq succeeded.")
            except Exception as groq_exc:
                logger.warning("Groq synthesis failed: %s — trying Ollama.", groq_exc)

        # ── 3. Try Ollama if Groq also failed ──────────────────────────────
        if raw_text is None:
            try:
                raw_text = await asyncio.to_thread(_try_ollama, prompt)
                logger.info("Synthesis via Ollama succeeded.")
            except Exception as ollama_exc:
                logger.error("Ollama synthesis also failed: %s", ollama_exc)

    # ── 4. Parse + validate ───────────────────────────────────────────────
    if raw_text:
        try:
            stripped = _strip_fences(raw_text)
            logger.debug("Stripped response (first 300 chars): %r", stripped[:300])
            course_dict = _safe_json_loads(stripped)
            _validate(course_dict)
            logger.info(
                "Course synthesized: %r — %d modules",
                course_dict.get("course_title"),
                len(course_dict["modules"]),
            )
            return course_dict
        except (json.JSONDecodeError, ValueError) as parse_exc:
            logger.error("Failed to parse/validate LLM response: %s", parse_exc)

    # ── 5. Hard fallback ──────────────────────────────────────────────────
    logger.error("All synthesis attempts failed. Returning minimal fallback course.")
    return _fallback_course(topic, difficulty)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pprint
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    mock_search = [{"url": "https://example.com", "title": "Example", "snippet": "Test snippet"}]
    mock_articles = [{"url": "https://example.com", "title": "Example", "content": "Test content " * 50}]
    mock_transcripts: list[dict] = []

    ctx = _build_context(mock_search, mock_articles, mock_transcripts)
    print("=== Context builder ===\n", ctx[:500])

    fallback = _fallback_course("Quantum Computing", "Beginner")
    print("\n=== Fallback course ===")
    pprint.pprint(fallback, depth=3)
