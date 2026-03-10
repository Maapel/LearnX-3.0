"""
youtube_service.py — LearnX 3.0
Fetches transcripts from YouTube videos using youtube-transcript-api.
"""

import logging
import re
import asyncio
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> str | None:
    """
    Extract the YouTube video ID from various URL formats:
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
      - https://youtube.com/shorts/VIDEO_ID
    Returns the video ID string, or None if it cannot be parsed.
    """
    try:
        parsed = urlparse(url)

        # youtu.be short links: path is /VIDEO_ID
        if parsed.netloc in ("youtu.be", "www.youtu.be"):
            video_id = parsed.path.lstrip("/").split("/")[0]
            if video_id:
                return video_id

        # youtube.com variants
        if parsed.netloc in ("youtube.com", "www.youtube.com", "m.youtube.com"):
            # /watch?v=VIDEO_ID
            if parsed.path == "/watch":
                qs = parse_qs(parsed.query)
                ids = qs.get("v", [])
                if ids:
                    return ids[0]

            # /embed/VIDEO_ID  or  /shorts/VIDEO_ID
            match = re.match(r"^/(?:embed|shorts|v)/([A-Za-z0-9_-]+)", parsed.path)
            if match:
                return match.group(1)

        logger.warning("Could not extract video ID from URL: %s", url)
        return None

    except Exception as exc:
        logger.error("Error parsing YouTube URL '%s': %s", url, exc)
        return None


async def get_transcript(url: str) -> dict:
    """
    Fetch the transcript for a YouTube video.

    Returns a dict with keys:
        video_id  : str
        url       : str
        transcript: str   — full joined transcript text
        success   : bool
        error     : str | None
    """
    result = {
        "video_id": None,
        "url": url,
        "transcript": "",
        "success": False,
        "error": None,
    }

    try:
        video_id = extract_video_id(url)
        if not video_id:
            result["error"] = f"Could not extract video ID from URL: {url}"
            logger.error(result["error"])
            return result

        result["video_id"] = video_id

        # Run the blocking API call in a thread pool so we don't block the event loop
        transcript_data = await asyncio.get_event_loop().run_in_executor(
            None, _fetch_transcript, video_id
        )

        if transcript_data is None:
            result["error"] = f"No transcript available for video ID: {video_id}"
            logger.error(result["error"])
            return result

        # Join all snippet texts into a single string
        full_text = " ".join(entry.get("text", "") for entry in transcript_data)
        result["transcript"] = full_text.strip()
        result["success"] = True
        logger.info(
            "Successfully fetched transcript for video '%s' (%d characters).",
            video_id,
            len(result["transcript"]),
        )

    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("Unexpected error fetching transcript for URL '%s': %s", url, exc)

    return result


def _fetch_transcript(video_id: str) -> list | None:
    """
    Synchronous helper: try English first, fall back to any available language.
    Returns a list of transcript snippet dicts, or None on failure.
    """
    # --- Attempt 1: English transcript ---
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
            logger.info("Found English transcript for video '%s'.", video_id)
            return transcript.fetch()
        except Exception:
            logger.warning(
                "No English transcript for '%s'. Trying any available language.", video_id
            )

        # --- Attempt 2: Any available language ---
        for transcript in transcript_list:
            try:
                data = transcript.fetch()
                logger.info(
                    "Using '%s' transcript for video '%s'.",
                    transcript.language_code,
                    video_id,
                )
                return data
            except Exception as lang_exc:
                logger.warning(
                    "Failed to fetch '%s' transcript: %s",
                    transcript.language_code,
                    lang_exc,
                )
                continue

        logger.error("All transcript languages failed for video '%s'.", video_id)
        return None

    except Exception as exc:
        logger.error("Could not list transcripts for video '%s': %s", video_id, exc)
        return None


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    TEST_URL = "https://www.youtube.com/watch?v=rfscVS0vtbw"

    print(f"\nTesting youtube_service.py with URL: {TEST_URL}\n")

    async def main():
        result = await get_transcript(TEST_URL)
        print("video_id :", result["video_id"])
        print("url      :", result["url"])
        print("success  :", result["success"])
        print("error    :", result["error"])
        if result["transcript"]:
            preview = result["transcript"][:300]
            print(f"transcript (first 300 chars):\n  {preview}...")
        else:
            print("transcript: (empty)")
        print("\nFull result (truncated transcript):")
        display = {**result, "transcript": result["transcript"][:200] + "..." if result["transcript"] else ""}
        print(json.dumps(display, indent=2))

    asyncio.run(main())
