"""
synthesizer.py — LearnX 3.0 Backend
Feeds scraped content into Gemini (with Groq fallback) and returns a
structured Course JSON matching the Pydantic Course schema.

Model cascade:
  1. gemini-1.5-flash   (Gemini free tier)
  2. gemini-1.5-flash-8b (smaller, higher free quota)
  3. Groq llama-3.3-70b  (fallback if Gemini quota exhausted)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Load keys from ../../.env relative to this file
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path)

from google import genai
from google.genai import types as genai_types
from groq import Groq

logger = logging.getLogger(__name__)

_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")

# Gemini model cascade — use full model path as required by google-genai v1 SDK
# gemini-2.0-flash-lite has the highest free-tier quota
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
          "content_markdown": "string (minimum 200 words of rich teaching content)",
          "key_takeaways": ["string", ...]
        }
      ]
    }
  ]
}

Rules:
- Create between 3 and 5 modules.
- Each module must have between 2 and 4 lessons.
- Every lesson's content_markdown MUST be at least 200 words of rich, educational markdown prose.
  Use headings (##, ###), bullet lists, code blocks, or numbered steps where appropriate.
- Synthesize information from the provided source material into content_markdown.
- Assign source_url to the most relevant URL from the provided sources when applicable; use null otherwise.
- Set content_type to "video" when the source is a YouTube transcript, "article" when based on a
  web article, and "concept_breakdown" for synthesized conceptual explanations.
- estimated_hours should be a realistic total study time (a float, e.g. 4.5).
- difficulty_level must match the requested difficulty exactly.
- Return ONLY valid JSON. No markdown code fences, no commentary, no extra text before or after.
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
def _validate(course_dict: dict) -> None:
    required = {"course_title", "difficulty_level", "estimated_hours", "modules"}
    missing = required - course_dict.keys()
    if missing:
        raise ValueError(f"Missing keys: {missing}")
    if not isinstance(course_dict["modules"], list) or not course_dict["modules"]:
        raise ValueError("No modules found")
    for mod in course_dict["modules"]:
        if "lessons" not in mod or not isinstance(mod["lessons"], list) or not mod["lessons"]:
            raise ValueError(f"Module '{mod.get('module_title')}' has no lessons")


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
                    "3. Retry the request.\n"
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
    """Try each Gemini model in order. Returns raw text or raises."""
    if not _GEMINI_API_KEY:
        raise RuntimeError("No GEMINI_API_KEY")

    client = genai.Client(api_key=_GEMINI_API_KEY)
    last_exc: Exception | None = None

    for model_name in _GEMINI_MODELS:
        try:
            logger.info("Trying Gemini model: %s", model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=0.7),
            )
            logger.info("Gemini %s succeeded.", model_name)
            return response.text
        except Exception as exc:
            logger.warning("Gemini %s failed: %s", model_name, exc)
            last_exc = exc

    raise RuntimeError(f"All Gemini models failed. Last error: {last_exc}")


# ---------------------------------------------------------------------------
# Groq synthesis fallback
# ---------------------------------------------------------------------------
def _try_groq(prompt: str) -> str:
    """Use Groq llama-3.3-70b as synthesis fallback. Returns raw text or raises."""
    if not _GROQ_API_KEY:
        raise RuntimeError("No GROQ_API_KEY")

    logger.info("Falling back to Groq (%s) for synthesis.", _GROQ_MODEL)
    client = Groq(api_key=_GROQ_API_KEY)
    response = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are an expert curriculum designer. Return ONLY valid JSON, no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=8192,
    )
    return response.choices[0].message.content


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
    Cascade: Gemini 1.5-flash → Gemini 1.5-flash-8b → Groq llama-3.3-70b → fallback.
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

    # ── 1. Try Gemini ─────────────────────────────────────────────────────
    try:
        raw_text = await asyncio.to_thread(_try_gemini, prompt)
        logger.info("Synthesis via Gemini succeeded.")
    except Exception as gemini_exc:
        logger.warning("Gemini synthesis failed: %s — trying Groq.", gemini_exc)

    # ── 2. Try Groq if Gemini failed ─────────────────────────────────────
    if raw_text is None:
        try:
            raw_text = await asyncio.to_thread(_try_groq, prompt)
            logger.info("Synthesis via Groq succeeded.")
        except Exception as groq_exc:
            logger.error("Groq synthesis also failed: %s", groq_exc)

    # ── 3. Parse + validate ───────────────────────────────────────────────
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

    # ── 4. Hard fallback ──────────────────────────────────────────────────
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
