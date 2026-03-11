"""
routers/course.py — LearnX 3.0
POST /api/generate-course: chains the sourcing engine + AI brain into one endpoint.
Includes a JSON file-backed course cache to skip the full pipeline on repeat requests.
"""

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from models import Course, CourseGenerateRequest
from services.llm_router import generate_search_queries
from services.search_service import search_web
from services.scraper_service import scrape_article
from services.youtube_service import get_transcript
from services.synthesizer import synthesize_course

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["course"])

YOUTUBE_DOMAINS = ("youtube.com", "youtu.be", "www.youtube.com")

# ---------------------------------------------------------------------------
# Course cache — JSON file on disk so it persists across server restarts
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)


def _normalize_intent(topic: str, difficulty: str) -> str:
    """Lowercase + collapse whitespace for stable cache keys."""
    topic_clean = re.sub(r"\s+", " ", topic.strip().lower())
    return f"{topic_clean}::{difficulty.lower()}"


def _cache_path(intent_key: str) -> Path:
    key_hash = hashlib.md5(intent_key.encode()).hexdigest()
    return _CACHE_DIR / f"{key_hash}.json"


def _load_from_cache(intent_key: str) -> dict | None:
    path = _cache_path(intent_key)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info("Course cache HIT for %r", intent_key)
            return data
        except Exception as exc:
            logger.warning("Cache read failed for %r: %s", intent_key, exc)
    return None


def _save_to_cache(intent_key: str, course_dict: dict) -> None:
    path = _cache_path(intent_key)
    try:
        path.write_text(json.dumps(course_dict, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Course cached → %s", path.name)
    except Exception as exc:
        logger.warning("Cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_youtube(url: str) -> bool:
    return any(domain in url for domain in YOUTUBE_DOMAINS)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/generate-course", response_model=Course)
async def generate_course(request: CourseGenerateRequest) -> Course:
    """
    Full pipeline:
      0. Check course cache — return immediately if this topic+difficulty was generated before
      1. Use Groq to generate 2 consolidated search queries
      2. Use Tavily (basic depth, cached) to fetch top URLs
      3. Concurrently scrape articles + fetch YouTube transcripts
      4. Use Gemini (structured output) → Groq → Ollama to synthesize a Course JSON
      5. Cache result and return
    """
    topic = request.topic.strip()
    difficulty = request.difficulty or "Beginner"
    intent_key = _normalize_intent(topic, difficulty)

    logger.info("Course request: topic=%r, difficulty=%r", topic, difficulty)

    # ── Step 0: Check course cache ────────────────────────────────────────────
    cached = _load_from_cache(intent_key)
    if cached:
        try:
            return Course(**cached)
        except Exception as exc:
            logger.warning("Cached course failed validation (%s) — regenerating.", exc)

    # ── Step 1: Generate search queries via Groq ──────────────────────────────
    try:
        queries = await generate_search_queries(topic, difficulty, num_queries=2)
        logger.info("Generated queries: %s", queries)
    except Exception as exc:
        logger.error("Query generation failed: %s", exc)
        queries = [f"{topic} {difficulty} tutorial guide", f"learn {topic} comprehensive overview"]

    # ── Step 2: Search the web (Tavily, basic, cached) ────────────────────────
    try:
        search_tasks = [search_web(q, num_results=3) for q in queries[:2]]
        search_batches = await asyncio.gather(*search_tasks, return_exceptions=True)

        seen_urls: set[str] = set()
        search_results: list[dict] = []
        for batch in search_batches:
            if isinstance(batch, Exception):
                logger.warning("A search batch failed: %s", batch)
                continue
            for item in batch:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    search_results.append(item)

        logger.info("Collected %d unique search results", len(search_results))
    except Exception as exc:
        logger.error("Search step failed entirely: %s", exc)
        search_results = []

    if not search_results:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve any search results. Check TAVILY_API_KEY.",
        )

    # ── Step 3: Concurrently scrape articles + fetch transcripts ──────────────
    urls = [r["url"] for r in search_results[:6]]  # cap at 6 URLs (down from 8)
    youtube_urls = [u for u in urls if _is_youtube(u)]
    article_urls = [u for u in urls if not _is_youtube(u)]

    scrape_tasks = [scrape_article(u) for u in article_urls]
    transcript_tasks = [get_transcript(u) for u in youtube_urls]

    scrape_results_raw, transcript_results_raw = await asyncio.gather(
        asyncio.gather(*scrape_tasks, return_exceptions=True),
        asyncio.gather(*transcript_tasks, return_exceptions=True),
    )

    scraped_articles = [
        r for r in scrape_results_raw
        if not isinstance(r, Exception) and r.get("success")
    ]
    transcripts = [
        r for r in transcript_results_raw
        if not isinstance(r, Exception) and r.get("success")
    ]

    logger.info(
        "Sourcing complete: %d articles scraped, %d transcripts fetched",
        len(scraped_articles),
        len(transcripts),
    )

    # ── Step 4: Synthesize (Gemini structured → Groq → Ollama) ───────────────
    try:
        course_dict = await synthesize_course(
            topic=topic,
            difficulty=difficulty,
            search_results=search_results,
            scraped_articles=scraped_articles,
            transcripts=transcripts,
        )
    except Exception as exc:
        logger.error("Synthesis failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Course synthesis failed: {exc}")

    # ── Step 5: Validate, cache, return ──────────────────────────────────────
    try:
        course = Course(**course_dict)
    except Exception as exc:
        logger.error("Course schema validation failed: %s\nDict: %s", exc, course_dict)
        raise HTTPException(
            status_code=500,
            detail=f"Generated course failed schema validation: {exc}",
        )

    _save_to_cache(intent_key, course_dict)
    logger.info("Course generated successfully: %r", course.course_title)
    return course
