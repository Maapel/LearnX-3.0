"""
routers/course.py — LearnX 3.0
Two endpoints for Just-In-Time (rolling) generation:
  POST /api/generate-outline  — fast skeleton (<5s)
  POST /api/generate-lesson   — deep per-lesson content on demand
"""

import asyncio
import hashlib
import json
import logging
import math
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from models import CourseOutline, LessonDetail, OutlineGenerateRequest, LessonGenerateRequest
from services.search_service import search_web
from services.scraper_service import scrape_article
from services.youtube_service import get_transcript
from services.synthesizer import synthesize_outline, synthesize_lesson

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["course"])

YOUTUBE_DOMAINS = ("youtube.com", "youtu.be", "www.youtube.com")

# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"


def _load_cache(key: str) -> dict | None:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Cache read failed for %r: %s", key, e)
    return None


def _save_cache(key: str, data: dict) -> None:
    try:
        _cache_path(key).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        logger.warning("Cache write failed: %s", e)


def _is_youtube(url: str) -> bool:
    return any(d in url for d in YOUTUBE_DOMAINS)


# ---------------------------------------------------------------------------
# Shared sourcing helper
# ---------------------------------------------------------------------------

async def _source_content(queries: list[str], difficulty: str) -> tuple[list, list, list]:
    """Search + scrape + transcripts using the provided queries. Returns (search, articles, transcripts)."""
    try:
        batches = await asyncio.gather(*[search_web(q, num_results=3) for q in queries[:2]], return_exceptions=True)
        seen: set[str] = set()
        search_results: list[dict] = []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                url = item.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    search_results.append(item)
    except Exception:
        search_results = []

    urls = [r["url"] for r in search_results[:6]]
    yt_urls = [u for u in urls if _is_youtube(u)]
    art_urls = [u for u in urls if not _is_youtube(u)]

    scrape_raw, transcript_raw = await asyncio.gather(
        asyncio.gather(*[scrape_article(u) for u in art_urls], return_exceptions=True),
        asyncio.gather(*[get_transcript(u) for u in yt_urls], return_exceptions=True),
    )

    articles = [r for r in scrape_raw if not isinstance(r, Exception) and r.get("success")]
    transcripts = [r for r in transcript_raw if not isinstance(r, Exception) and r.get("success")]

    return search_results, articles, transcripts


# ---------------------------------------------------------------------------
# POST /api/generate-outline
# ---------------------------------------------------------------------------

@router.post("/generate-outline", response_model=CourseOutline)
async def generate_outline(request: OutlineGenerateRequest) -> CourseOutline:
    """
    Fast endpoint — returns a CourseOutline (title + module/lesson skeleton).
    No content, no exercises. Should complete in < 5 seconds.
    Cached on disk by topic+difficulty.
    """
    topic = request.topic.strip()
    difficulty = request.difficulty or "Beginner"
    cache_key = f"outline::{_normalize(topic)}::{difficulty.lower()}"

    cached = _load_cache(cache_key)
    if cached:
        logger.info("Outline cache HIT: %r", topic)
        try:
            return CourseOutline(**cached)
        except Exception as e:
            logger.warning("Cached outline invalid (%s) — regenerating", e)

    logger.info("Generating outline: topic=%r, difficulty=%r (includes lesson_context + queries)", topic, difficulty)
    outline_dict = await synthesize_outline(topic, difficulty)

    try:
        outline = CourseOutline(**outline_dict)
    except Exception as exc:
        logger.error("Outline validation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Outline validation failed: {exc}")

    _save_cache(cache_key, outline_dict)
    return outline


# ---------------------------------------------------------------------------
# POST /api/generate-lesson
# ---------------------------------------------------------------------------

@router.post("/generate-lesson", response_model=LessonDetail)
async def generate_lesson(request: LessonGenerateRequest) -> LessonDetail:
    """
    JIT endpoint — generates rich interactive content for a single lesson.
    Runs sourcing (search + scrape) scoped to the specific lesson topic.
    Cached on disk by lesson_id.
    """
    cache_key = f"lesson::{request.lesson_id}"
    cached = _load_cache(cache_key)
    if cached:
        if len(cached.get("sections", [])) >= 2:
            logger.info("Lesson cache HIT: %r", request.lesson_title)
            try:
                return LessonDetail(**cached)
            except Exception as e:
                logger.warning("Cached lesson invalid (%s) — regenerating", e)
        else:
            logger.info("Lesson cache STALE (fallback content) for %r — regenerating", request.lesson_title)

    logger.info(
        "Generating lesson: %r | queries: %s",
        request.lesson_title, request.target_search_queries,
    )

    # Use the pre-planned queries from the outline instead of guessing
    search_results, articles, transcripts = await _source_content(
        queries=request.target_search_queries,
        difficulty=request.difficulty,
    )

    lesson_dict = await synthesize_lesson(
        lesson_id=request.lesson_id,
        lesson_title=request.lesson_title,
        lesson_context=request.lesson_context,
        course_title=request.course_title,
        difficulty=request.difficulty,
        search_results=search_results,
        scraped_articles=articles,
        transcripts=transcripts,
    )

    # Calculate reading time from word count — never trust the LLM to estimate this
    total_words = sum(
        len(s.get("explanation", "").split())
        for s in lesson_dict.get("sections", [])
    )
    lesson_dict["estimated_time_minutes"] = max(1, math.ceil(total_words / 200))
    logger.info("Calculated reading time: %d min (%d words)", lesson_dict["estimated_time_minutes"], total_words)

    # Inject real sources from search results (non-YouTube only, deduplicated, max 5)
    YOUTUBE_DOMAINS_SET = set(YOUTUBE_DOMAINS)
    seen_urls: set[str] = set()
    sources = []
    for r in search_results:
        url = r.get("url", "").strip()
        title = r.get("title", "").strip()
        if not url or not title:
            continue
        if any(d in url for d in YOUTUBE_DOMAINS_SET):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append({
            "title": title,
            "url": url,
            "snippet": r.get("snippet", "")[:200],
        })
        if len(sources) >= 5:
            break
    lesson_dict["sources"] = sources

    try:
        lesson = LessonDetail(**lesson_dict)
    except Exception as exc:
        logger.error("Lesson validation failed: %s\nDict: %s", exc, lesson_dict)
        raise HTTPException(status_code=500, detail=f"Lesson validation failed: {exc}")

    # Only cache lessons with real content — never cache static fallback (1 section)
    if len(lesson_dict.get("sections", [])) >= 2:
        _save_cache(cache_key, lesson_dict)
    else:
        logger.warning("Lesson %r has only %d section(s) — skipping cache (likely fallback)",
                       request.lesson_title, len(lesson_dict.get("sections", [])))
    return lesson
