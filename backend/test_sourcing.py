"""
test_sourcing.py — LearnX 3.0 HITL Checkpoint: Phase 2
Run this script to verify all sourcing services work before Phase 3.

Usage:
    cd backend
    source venv/bin/activate
    python test_sourcing.py
"""
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from services.search_service import search_web, get_search_queries
from services.youtube_service import get_transcript
from services.scraper_service import scrape_article

DIVIDER = "=" * 60
TEST_TOPIC = "Python programming"
TEST_YOUTUBE_URL = "https://www.youtube.com/watch?v=rfscVS0vtbw"
TEST_ARTICLE_URL = "https://realpython.com/python-basics/"


async def test_search():
    print(f"\n{DIVIDER}")
    print("TEST 1: Search Service (Tavily)")
    print(DIVIDER)
    print(f"Topic: {TEST_TOPIC}")
    queries = get_search_queries(TEST_TOPIC)
    print(f"Generated queries: {queries}")
    results = await search_web(TEST_TOPIC, num_results=3)
    if not results:
        print("❌ FAILED: No results returned. Check TAVILY_API_KEY in .env")
        return False
    print(f"✅ Got {len(results)} results:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['title']}")
        print(f"     URL: {r['url']}")
        print(f"     Snippet: {r['snippet'][:120]}...")
    return True


async def test_youtube():
    print(f"\n{DIVIDER}")
    print("TEST 2: YouTube Transcript Service")
    print(DIVIDER)
    print(f"URL: {TEST_YOUTUBE_URL}")
    result = await get_transcript(TEST_YOUTUBE_URL)
    if not result["success"]:
        print(f"❌ FAILED: {result['error']}")
        return False
    transcript_preview = result["transcript"][:300]
    print(f"✅ Got transcript for video ID: {result['video_id']}")
    print(f"   Length: {len(result['transcript'])} chars")
    print(f"   Preview: {transcript_preview}...")
    return True


async def test_scraper():
    print(f"\n{DIVIDER}")
    print("TEST 3: Web Scraper Service")
    print(DIVIDER)
    print(f"URL: {TEST_ARTICLE_URL}")
    result = await scrape_article(TEST_ARTICLE_URL)
    if not result["success"]:
        print(f"❌ FAILED: {result['error']}")
        return False
    print(f"✅ Scraped article: '{result['title']}'")
    print(f"   Word count: {result['word_count']}")
    print(f"   Preview: {result['content'][:300]}...")
    return True


async def main():
    print("\n" + DIVIDER)
    print("  LearnX 3.0 — Phase 2 HITL Sourcing Test")
    print(DIVIDER)

    results = await asyncio.gather(
        test_search(),
        test_youtube(),
        test_scraper(),
        return_exceptions=True,
    )

    search_ok = results[0] if not isinstance(results[0], Exception) else False
    youtube_ok = results[1] if not isinstance(results[1], Exception) else False
    scraper_ok = results[2] if not isinstance(results[2], Exception) else False

    print(f"\n{DIVIDER}")
    print("SUMMARY")
    print(DIVIDER)
    print(f"  Search Service:   {'✅ PASS' if search_ok else '❌ FAIL'}")
    print(f"  YouTube Service:  {'✅ PASS' if youtube_ok else '❌ FAIL'}")
    print(f"  Scraper Service:  {'✅ PASS' if scraper_ok else '❌ FAIL'}")
    print(DIVIDER)

    all_pass = all([search_ok, youtube_ok, scraper_ok])
    if all_pass:
        print("\n✅ All sourcing services operational. Ready for Phase 3.")
    else:
        print("\n⚠️  Some services failed. Fix issues above before Phase 3.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
