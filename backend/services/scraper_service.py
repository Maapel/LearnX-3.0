"""
scraper_service.py — LearnX 3.0 Backend
Fetches an article URL and extracts clean main body text.

Primary:  Cloudflare Browser Rendering crawl API (returns markdown directly)
Fallback: httpx + BeautifulSoup (when CF credentials are missing or CF fails)
"""

import asyncio
import logging
import os
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIMEOUT = 15  # seconds
MAX_WORDS = 8000
MAX_CHARS = 15000  # hard character cap per URL — keeps LLM token usage predictable

_CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
_CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Tags whose entire subtree should be stripped before text extraction
NOISE_TAGS = ["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "svg", "noscript", "picture"]

# CSS selectors tried in priority order for main content
CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".post-content",
    ".entry-content",
    ".article-body",
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _collapse_blank_lines(text: str) -> str:
    """Collapse sequences of more than two consecutive blank lines into two."""
    return re.sub(r"\n{3,}", "\n\n", text)


def _cap_words(text: str, max_words: int = MAX_WORDS) -> str:
    """Truncate text to at most *max_words* words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _extract_text(soup: BeautifulSoup) -> str:
    """
    Remove noise tags, locate the best content container, and return
    cleaned text.
    """
    # Strip noise subtrees in-place
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Try each content selector in priority order
    container = None
    for selector in CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container:
            break

    # Fall back to <body> if no specific container was found
    if container is None:
        container = soup.find("body")

    # Last resort: use the whole document
    if container is None:
        container = soup

    raw_text = container.get_text(separator="\n", strip=True)
    return _collapse_blank_lines(raw_text)


# ---------------------------------------------------------------------------
# Cloudflare Browser Rendering crawl API
# ---------------------------------------------------------------------------


async def _scrape_via_cloudflare(url: str) -> dict | None:
    """Use CF Browser Rendering crawl endpoint. Returns result dict or None on failure."""
    if not _CF_ACCOUNT_ID or not _CF_API_TOKEN:
        return None

    cf_url = f"https://api.cloudflare.com/client/v4/accounts/{_CF_ACCOUNT_ID}/browser-rendering/crawl"
    headers = {
        "Authorization": f"Bearer {_CF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "limit": 1,
        "formats": ["markdown"],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # POST to start crawl
            resp = await client.post(cf_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                logger.warning("CF crawl POST failed: %s", data.get("errors"))
                return None

            job_id = data.get("result", {}).get("id")
            if not job_id:
                logger.warning("CF crawl returned no job ID")
                return None

            # Poll for results (max 10 attempts, 2s apart)
            for attempt in range(10):
                await asyncio.sleep(2)
                poll = await client.get(f"{cf_url}/{job_id}", headers=headers)
                poll.raise_for_status()
                poll_data = poll.json()

                result = poll_data.get("result", {})
                status = result.get("status", "")

                if status == "completed":
                    records = result.get("records", [])
                    if not records:
                        return None

                    record = records[0]
                    markdown = record.get("markdown", "")
                    if not markdown:
                        return None

                    content = _cap_words(markdown)
                    content = content[:MAX_CHARS]

                    title = record.get("title", "") or url
                    word_count = len(content.split())
                    logger.info("CF crawl success: '%s' — %d words", title, word_count)

                    return {
                        "url": url,
                        "title": title,
                        "content": content,
                        "word_count": word_count,
                        "success": True,
                        "error": None,
                    }

                if status in ("errored", "cancelled_due_to_timeout"):
                    logger.warning("CF crawl %s for %s", status, url)
                    return None

            logger.warning("CF crawl timed out polling for %s", url)
            return None

    except Exception as exc:
        logger.warning("CF crawl error for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Fallback: httpx + BeautifulSoup
# ---------------------------------------------------------------------------


async def _scrape_via_httpx(url: str) -> dict:
    """Fetch URL with httpx and parse with BeautifulSoup."""
    result: dict = {
        "url": url,
        "title": "",
        "content": "",
        "word_count": 0,
        "success": False,
        "error": None,
    }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=TIMEOUT,
            headers=HEADERS,
        ) as client:
            logger.info("Fetching URL (httpx fallback): %s", url)
            response = await client.get(url)
            response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title_tag = soup.find("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else ""

        # Extract, cap words, then hard-cap characters
        content = _extract_text(soup)
        content = _cap_words(content)
        content = content[:MAX_CHARS]

        result["content"] = content
        result["word_count"] = len(content.split())
        result["success"] = True
        logger.info(
            "Scraped '%s' — %d words extracted.", result["title"], result["word_count"]
        )

    except httpx.HTTPStatusError as exc:
        msg = f"HTTP error {exc.response.status_code} for URL: {url}"
        logger.error(msg)
        result["error"] = msg
    except httpx.RequestError as exc:
        msg = f"Request error while fetching {url}: {exc}"
        logger.error(msg)
        result["error"] = msg
    except Exception as exc:  # noqa: BLE001
        msg = f"Unexpected error scraping {url}: {exc}"
        logger.exception(msg)
        result["error"] = msg

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def scrape_article(url: str) -> dict:
    """
    Fetch *url* and return a dict with extracted article content.
    Tries Cloudflare Browser Rendering first, falls back to httpx+BS4.

    Returns
    -------
    {
        "url": str,
        "title": str,
        "content": str,
        "word_count": int,
        "success": bool,
        "error": str | None,
    }
    """
    # Try Cloudflare first
    cf_result = await _scrape_via_cloudflare(url)
    if cf_result:
        return cf_result

    # Fallback to httpx + BeautifulSoup
    return await _scrape_via_httpx(url)


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    TEST_URL = "https://realpython.com/python-basics/"

    async def _main() -> None:
        data = await scrape_article(TEST_URL)
        print("\n--- scraper_service smoke test ---")
        print(f"URL      : {data['url']}")
        print(f"Title    : {data['title']}")
        print(f"Success  : {data['success']}")
        print(f"Words    : {data['word_count']}")
        print(f"Error    : {data['error']}")
        print("\n--- Content preview (first 500 chars) ---")
        print(data["content"][:500])

    asyncio.run(_main())
