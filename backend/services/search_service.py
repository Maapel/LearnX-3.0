import asyncio
import hashlib
import logging
import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logger = logging.getLogger(__name__)

# High-signal educational domains — avoids wasting credits on low-quality pages
_EDUCATIONAL_DOMAINS = [
    "github.com",
    "medium.com",
    "freecodecamp.org",
    "dev.to",
    "wikipedia.org",
    "youtube.com",
    "realpython.com",
    "docs.python.org",
    "geeksforgeeks.org",
    "towardsdatascience.com",
]

# In-process search cache: query_hash → list[dict]
_search_cache: dict[str, list[dict]] = {}


def _cache_key(query: str, num_results: int) -> str:
    return hashlib.md5(f"{query.strip().lower()}:{num_results}".encode()).hexdigest()


async def search_web(topic: str, num_results: int = 5) -> list[dict]:
    """
    Search the web for a given topic using the Tavily API.

    Optimizations:
    - search_depth="basic"  → half the credit cost vs "advanced"
    - include_raw_content=False → no extra credit charge for full page HTML
    - include_domains → restricts to high-signal educational sites
    - In-memory cache → zero API calls for repeated queries within same session
    """
    cache_key = _cache_key(topic, num_results)
    if cache_key in _search_cache:
        logger.info("search_web: cache hit for %r", topic)
        return _search_cache[cache_key]

    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            logger.error("TAVILY_API_KEY is not set in environment variables.")
            return []

        client = TavilyClient(api_key=api_key)

        try:
            response = await asyncio.to_thread(
                client.search,
                query=topic,
                max_results=num_results,
                search_depth="basic",
                include_raw_content=False,
                include_domains=_EDUCATIONAL_DOMAINS,
            )
        except Exception as e:
            logger.error("Error calling Tavily API: %s", e)
            return []

        results = []
        for item in response.get("results", [])[:num_results]:
            try:
                results.append(
                    {
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("content", ""),
                    }
                )
            except Exception as e:
                logger.error("Error parsing search result item: %s", e)
                continue

        _search_cache[cache_key] = results
        logger.info("search_web: %d results cached for %r", len(results), topic)
        return results

    except Exception as e:
        logger.error("Unexpected error in search_web: %s", e)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        print("Searching for: Python programming")
        results = await search_web("Python programming")
        if not results:
            print("No results returned.")
        for i, result in enumerate(results, start=1):
            print(f"\nResult {i}:")
            print(f"  Title:   {result['title']}")
            print(f"  URL:     {result['url']}")
            print(f"  Snippet: {result['snippet'][:200]}...")

        # Second call should be a cache hit
        print("\n--- Second call (should hit cache) ---")
        results2 = await search_web("Python programming")
        print(f"Got {len(results2)} results (from cache)")

    asyncio.run(main())
