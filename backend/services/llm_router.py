import asyncio
import json
import logging
import os

import httpx
from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logger = logging.getLogger(__name__)

_GROQ_MODEL      = "llama-3.3-70b-versatile"
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
_OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.2")


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables.")
    return Groq(api_key=api_key)


def _call_ollama(system_prompt: str, user_message: str) -> str:
    """Call local Ollama model. Returns raw content string or raises."""
    url = f"{_OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": _OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {"temperature": 0.7},
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"]


def _strip_json_fences(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return cleaned


async def generate_search_queries(
    topic: str,
    difficulty: str = "Beginner",
    num_queries: int = 5,
) -> list[str]:
    """
    Generate targeted search queries for a learning topic.
    Cascade: Groq → Ollama → basic query fallback.
    """
    system_prompt = (
        f"You are a curriculum designer. Given a topic and difficulty level, "
        f"generate exactly {num_queries} specific search queries to find the best learning resources.\n"
        "Return ONLY a valid JSON array of strings, no other text. "
        'Example: ["query 1", "query 2"]'
    )
    user_message = f"Topic: {topic}\nDifficulty: {difficulty}"

    raw_content: str | None = None

    # ── 1. Try Groq ──────────────────────────────────────────────────────
    def _groq_call() -> str:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        return response.choices[0].message.content

    try:
        raw_content = await asyncio.to_thread(_groq_call)
        logger.info("generate_search_queries: Groq succeeded.")
    except Exception as groq_exc:
        logger.warning("generate_search_queries: Groq failed (%s) — trying Ollama.", groq_exc)

    # ── 2. Try Ollama ─────────────────────────────────────────────────────
    if raw_content is None:
        try:
            raw_content = await asyncio.to_thread(_call_ollama, system_prompt, user_message)
            logger.info("generate_search_queries: Ollama succeeded.")
        except Exception as ollama_exc:
            logger.warning("generate_search_queries: Ollama failed (%s) — using basic queries.", ollama_exc)

    # ── 3. Parse or fall back ─────────────────────────────────────────────
    if raw_content:
        try:
            cleaned = _strip_json_fences(raw_content)
            queries = json.loads(cleaned)
            if not isinstance(queries, list):
                raise ValueError(f"Expected a JSON array, got: {type(queries)}")
            queries = [str(q) for q in queries]
            logger.info("Generated %d search queries for topic '%s'.", len(queries), topic)
            return queries
        except Exception as parse_exc:
            logger.error("generate_search_queries: parse failed: %s", parse_exc)

    logger.warning("generate_search_queries: all providers failed, using basic queries.")
    return [
        f"{topic} tutorial",
        f"learn {topic}",
        f"{topic} for {difficulty.lower()}s",
        f"{topic} getting started guide",
        f"best resources to learn {topic}",
    ][:num_queries]


async def parse_learning_intent(topic: str) -> dict:
    """
    Decompose a learning topic into subtopics and recommended difficulty.
    Cascade: Groq → Ollama → default dict.
    """
    system_prompt = (
        "You are an expert curriculum designer. Given a learning topic, decompose it into "
        "3 to 5 meaningful subtopics and recommend an appropriate difficulty level.\n"
        "Return ONLY a valid JSON object with exactly these keys:\n"
        '  "topic": string,\n'
        '  "subtopics": array of 3-5 strings,\n'
        '  "recommended_difficulty": one of "Beginner", "Intermediate", or "Advanced"\n'
        "No other text outside the JSON object."
    )
    user_message = f"Learning topic: {topic}"

    raw_content: str | None = None

    # ── 1. Try Groq ──────────────────────────────────────────────────────
    def _groq_call() -> str:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            max_tokens=512,
        )
        return response.choices[0].message.content

    try:
        raw_content = await asyncio.to_thread(_groq_call)
        logger.info("parse_learning_intent: Groq succeeded.")
    except Exception as groq_exc:
        logger.warning("parse_learning_intent: Groq failed (%s) — trying Ollama.", groq_exc)

    # ── 2. Try Ollama ─────────────────────────────────────────────────────
    if raw_content is None:
        try:
            raw_content = await asyncio.to_thread(_call_ollama, system_prompt, user_message)
            logger.info("parse_learning_intent: Ollama succeeded.")
        except Exception as ollama_exc:
            logger.warning("parse_learning_intent: Ollama failed (%s) — using default.", ollama_exc)

    # ── 3. Parse or fall back ─────────────────────────────────────────────
    if raw_content:
        try:
            cleaned = _strip_json_fences(raw_content)
            result = json.loads(cleaned)
            if not isinstance(result, dict):
                raise ValueError(f"Expected a JSON object, got: {type(result)}")
            parsed = {
                "topic": str(result.get("topic", topic)),
                "subtopics": [str(s) for s in result.get("subtopics", [])],
                "recommended_difficulty": str(result.get("recommended_difficulty", "Beginner")),
            }
            if not parsed["subtopics"]:
                raise ValueError("Empty subtopics list.")
            logger.info(
                "Parsed intent for '%s': %d subtopics, difficulty=%s.",
                topic, len(parsed["subtopics"]), parsed["recommended_difficulty"],
            )
            return parsed
        except Exception as parse_exc:
            logger.error("parse_learning_intent: parse failed: %s", parse_exc)

    logger.warning("parse_learning_intent: all providers failed, returning default.")
    return {
        "topic": topic,
        "subtopics": [
            f"Introduction to {topic}",
            f"Core concepts of {topic}",
            f"Practical applications of {topic}",
        ],
        "recommended_difficulty": "Beginner",
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    async def main():
        test_topic = "Quantum Computing"
        test_difficulty = "Beginner"

        print(f"\n--- Testing generate_search_queries ---")
        queries = await generate_search_queries(topic=test_topic, difficulty=test_difficulty)
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")

        print(f"\n--- Testing parse_learning_intent ---")
        intent = await parse_learning_intent(topic=test_topic)
        print(f"  Topic:      {intent['topic']}")
        print(f"  Difficulty: {intent['recommended_difficulty']}")
        for i, s in enumerate(intent["subtopics"], 1):
            print(f"    {i}. {s}")

    asyncio.run(main())
