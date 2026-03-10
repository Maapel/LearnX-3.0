"""
synthesizer.py — LearnX 3.0 Backend
Feeds scraped content into Gemini and forces it to return a structured
Course JSON matching the Pydantic Course schema.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

# Load GEMINI_API_KEY from ../../.env relative to this file
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini configuration
# ---------------------------------------------------------------------------
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_MODEL_NAME = "gemini-2.0-flash"

# ---------------------------------------------------------------------------
# Schema description used inside the system prompt
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
# Helper: build context string from all sources
# ---------------------------------------------------------------------------
def _build_context(
    search_results: list[dict],
    scraped_articles: list[dict],
    transcripts: list[dict],
) -> str:
    """Assemble source material into a readable context block for the prompt."""
    parts: list[str] = []

    if search_results:
        parts.append("=== WEB SEARCH RESULTS ===")
        for i, result in enumerate(search_results, start=1):
            url = result.get("url", "")
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            parts.append(f"[{i}] {title}\nURL: {url}\nSnippet: {snippet}\n")

    if scraped_articles:
        parts.append("=== SCRAPED ARTICLES ===")
        for i, article in enumerate(scraped_articles, start=1):
            url = article.get("url", "")
            title = article.get("title", "")
            content = article.get("content", "")
            # Truncate to 2000 characters
            truncated = content[:2000]
            if len(content) > 2000:
                truncated += "\n[... content truncated ...]"
            parts.append(f"[Article {i}] {title}\nURL: {url}\n{truncated}\n")

    if transcripts:
        parts.append("=== YOUTUBE TRANSCRIPTS ===")
        for i, transcript_obj in enumerate(transcripts, start=1):
            url = transcript_obj.get("url", "")
            transcript_text = transcript_obj.get("transcript", "")
            # Truncate to 1500 characters
            truncated = transcript_text[:1500]
            if len(transcript_text) > 1500:
                truncated += "\n[... transcript truncated ...]"
            parts.append(f"[Video {i}] URL: {url}\nTranscript:\n{truncated}\n")

    if not parts:
        return "No source material was provided. Generate the course from your own knowledge."

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Fallback course builder
# ---------------------------------------------------------------------------
def _fallback_course(topic: str, difficulty: str) -> dict:
    """Return a minimal valid Course dict when synthesis fails."""
    return {
        "course_title": f"Introduction to {topic}",
        "difficulty_level": difficulty if difficulty in ("Beginner", "Intermediate", "Advanced") else "Beginner",
        "estimated_hours": 1.0,
        "modules": [
            {
                "module_title": f"Getting Started with {topic}",
                "module_description": (
                    f"A foundational overview of {topic} to get you up and running."
                ),
                "lessons": [
                    {
                        "lesson_title": f"What is {topic}?",
                        "content_type": "concept_breakdown",
                        "source_url": None,
                        "content_markdown": (
                            f"## What is {topic}?\n\n"
                            f"{topic} is a subject worth exploring deeply. "
                            "Unfortunately, the AI synthesis step encountered an error while "
                            "generating the full course content. This fallback lesson is provided "
                            "so you have a starting point.\n\n"
                            "### What you should know\n\n"
                            f"- {topic} is a broad and important area of study.\n"
                            "- There are many high-quality resources available online.\n"
                            "- Consider searching for introductory tutorials, official documentation, "
                            "and community forums to get started.\n\n"
                            "### Suggested next steps\n\n"
                            "1. Search for beginner-friendly guides on this topic.\n"
                            "2. Find a video course or playlist that walks through the fundamentals.\n"
                            "3. Practice hands-on by working through small exercises.\n"
                            "4. Join communities (forums, Discord servers, subreddits) to ask questions.\n\n"
                            "### Why learning this matters\n\n"
                            f"Understanding {topic} can open up new opportunities and deepen your "
                            "technical knowledge. Even a basic grasp of the fundamentals will help "
                            "you build more complex skills over time. Stay curious, be patient with "
                            "yourself, and revisit material as many times as you need to."
                        ),
                        "key_takeaways": [
                            f"{topic} is an important area of study.",
                            "Start with foundational concepts before moving to advanced topics.",
                            "Practice and hands-on projects accelerate learning.",
                        ],
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Main synthesis function
# ---------------------------------------------------------------------------
async def synthesize_course(
    topic: str,
    difficulty: str,
    search_results: list[dict],
    scraped_articles: list[dict],
    transcripts: list[dict],
) -> dict:
    """
    Feed scraped content into Gemini and return a Course-compatible dict.

    Parameters
    ----------
    topic           : The learning topic requested by the user.
    difficulty      : "Beginner", "Intermediate", or "Advanced".
    search_results  : Output from search_service — list of {url, title, snippet}.
    scraped_articles: Output from scraper_service — list of {url, title, content}.
    transcripts     : Output from youtube_service — list of {url, transcript}.

    Returns
    -------
    A dict matching the Course Pydantic schema.
    """
    if not _GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Returning fallback course.")
        return _fallback_course(topic, difficulty)

    try:
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

        logger.info("Sending synthesis request to Gemini for topic: %r", topic)

        client = genai.Client(api_key=_GEMINI_API_KEY)

        def _call_gemini() -> str:
            response = client.models.generate_content(
                model=_MODEL_NAME,
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=0.7),
            )
            return response.text

        # Run the synchronous Gemini call in a thread to avoid blocking the event loop
        raw_text = await asyncio.to_thread(_call_gemini)
        raw_text = raw_text.strip()
        logger.debug("Raw Gemini response (first 500 chars): %s", raw_text[:500])

        # Strip markdown code fences if Gemini added them despite instructions
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            # Remove the first line (``` or ```json) and the last ``` line
            inner_lines = []
            skip_first = True
            for line in lines:
                if skip_first and line.startswith("```"):
                    skip_first = False
                    continue
                if line.strip() == "```" and not skip_first:
                    break
                inner_lines.append(line)
            raw_text = "\n".join(inner_lines).strip()

        course_dict = json.loads(raw_text)

        # Basic structural validation
        required_keys = {"course_title", "difficulty_level", "estimated_hours", "modules"}
        if not required_keys.issubset(course_dict.keys()):
            missing = required_keys - course_dict.keys()
            raise ValueError(f"Gemini response missing required keys: {missing}")

        if not isinstance(course_dict["modules"], list) or len(course_dict["modules"]) == 0:
            raise ValueError("Gemini response contains no modules.")

        for mod in course_dict["modules"]:
            if "lessons" not in mod or not isinstance(mod["lessons"], list):
                raise ValueError(f"Module {mod.get('module_title')} has no valid lessons list.")

        logger.info(
            "Synthesis complete: %r — %d modules",
            course_dict.get("course_title"),
            len(course_dict["modules"]),
        )
        return course_dict

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Gemini response as JSON: %s", exc)
        return _fallback_course(topic, difficulty)
    except ValueError as exc:
        logger.error("Gemini response failed schema validation: %s", exc)
        return _fallback_course(topic, difficulty)
    except Exception as exc:
        logger.exception("Unexpected error during Gemini synthesis: %s", exc)
        return _fallback_course(topic, difficulty)


# ---------------------------------------------------------------------------
# Manual smoke test (no real API call)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pprint

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    # Mock data — mirrors what the sourcing services return
    mock_search_results = [
        {
            "url": "https://en.wikipedia.org/wiki/Quantum_computing",
            "title": "Quantum computing - Wikipedia",
            "snippet": "Quantum computing is a type of computation that harnesses quantum mechanical phenomena...",
        },
        {
            "url": "https://www.ibm.com/topics/quantum-computing",
            "title": "What is Quantum Computing? | IBM",
            "snippet": "Quantum computers use qubits, which can represent 0 and 1 simultaneously via superposition...",
        },
    ]

    mock_scraped_articles = [
        {
            "url": "https://www.ibm.com/topics/quantum-computing",
            "title": "What is Quantum Computing? | IBM",
            "content": (
                "Quantum computing leverages the principles of quantum mechanics to process information "
                "in ways that classical computers cannot. Unlike classical bits that are either 0 or 1, "
                "qubits can exist in superposition — both 0 and 1 at the same time. This allows quantum "
                "computers to evaluate many possibilities simultaneously. Entanglement is another key "
                "phenomenon: two qubits can be linked so that the state of one instantly influences the "
                "other, regardless of distance. Quantum interference is used to amplify correct answers "
                "and cancel out incorrect ones. " * 5  # repeat to simulate a longer article
            ),
        }
    ]

    mock_transcripts = [
        {
            "url": "https://www.youtube.com/watch?v=example123",
            "transcript": (
                "Welcome to this introduction to quantum computing. "
                "Today we'll cover what qubits are, how superposition works, "
                "and why quantum computers are different from classical ones. "
                "A qubit can be a photon, an electron, or a superconducting circuit. "
                "The magic is that until you measure it, it can be in a superposition of states. " * 10
            ),
        }
    ]

    print("=== Testing _build_context() ===\n")
    ctx = _build_context(mock_search_results, mock_scraped_articles, mock_transcripts)
    print(ctx[:1000])
    print("\n[... truncated for display ...]\n")

    print("=== Testing _fallback_course() ===\n")
    fallback = _fallback_course("Quantum Computing", "Beginner")
    pprint.pprint(fallback, depth=4)

    print("\n=== Context builder test passed. ===")
    print("To test the full synthesize_course() function, set GEMINI_API_KEY in .env and run:")
    print("  python -c \"import asyncio; from services.synthesizer import synthesize_course; ...")
