"""
routers/course.py — LearnX 3.0
POST /api/generate-course: chains the sourcing engine + AI brain into one endpoint.
"""

import asyncio
import logging

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


def _is_youtube(url: str) -> bool:
    return any(domain in url for domain in YOUTUBE_DOMAINS)


@router.post("/generate-course", response_model=Course)
async def generate_course(request: CourseGenerateRequest) -> Course:
    """
    Full pipeline:
      1. Use Groq to generate search queries from the topic
      2. Use Tavily to fetch top URLs
      3. Concurrently scrape articles + fetch YouTube transcripts
      4. Use Gemini to synthesize a structured Course JSON
    """
    topic = request.topic.strip()
    difficulty = request.difficulty or "Beginner"

    logger.info("Starting course generation for topic=%r, difficulty=%r", topic, difficulty)

    # ── Step 1: Generate search queries via Groq ──────────────────────────────
    try:
        queries = await generate_search_queries(topic, difficulty, num_queries=2)
        logger.info("Generated queries: %s", queries)
    except Exception as exc:
        logger.error("Query generation failed: %s", exc)
        queries = [f"{topic} {difficulty} tutorial guide", f"learn {topic} comprehensive overview"]

    # ── Step 2: Search the web for each query (take first 3 queries) ─────────
    try:
        search_tasks = [search_web(q, num_results=3) for q in queries[:2]]
        search_batches = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Flatten + deduplicate by URL
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
    urls = [r["url"] for r in search_results[:8]]  # cap at 8 URLs
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

    # ── Step 4: Synthesize with Gemini ────────────────────────────────────────
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

    # ── Step 5: Validate + return ─────────────────────────────────────────────
    try:
        course = Course(**course_dict)
    except Exception as exc:
        logger.error("Course schema validation failed: %s\nDict: %s", exc, course_dict)
        raise HTTPException(
            status_code=500,
            detail=f"Generated course failed schema validation: {exc}",
        )

    logger.info("Course generated successfully: %r", course.course_title)
    return course
