import asyncio
import logging
import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logger = logging.getLogger(__name__)


def get_search_queries(topic: str) -> list[str]:
    """Returns 3 varied search query strings for a given topic."""
    return [
        f"{topic} tutorial",
        f"learn {topic} basics",
        f"{topic} for beginners",
    ]


async def search_web(topic: str, num_results: int = 5) -> list[dict]:
    """
    Search the web for a given topic using the Tavily API.

    Args:
        topic: The topic to search for.
        num_results: Number of results to return (default 5).

    Returns:
        A list of dicts with keys: url, title, snippet.
        Returns an empty list on failure.
    """
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
                search_depth="advanced",
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

    asyncio.run(main())
