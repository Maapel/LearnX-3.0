import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"


def _get_client() -> Groq:
    """Instantiate and return a Groq client using the API key from the environment."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables.")
    return Groq(api_key=api_key)


async def generate_search_queries(
    topic: str,
    difficulty: str = "Beginner",
    num_queries: int = 5,
) -> list[str]:
    """
    Use Groq to generate targeted search queries for a learning topic.

    Args:
        topic: The subject the user wants to learn.
        difficulty: Difficulty level (e.g. "Beginner", "Intermediate", "Advanced").
        num_queries: Number of search queries to generate.

    Returns:
        A list of search query strings.
        Falls back to basic queries on any failure.
    """
    system_prompt = (
        f"You are a curriculum designer. Given a topic and difficulty level, "
        f"generate exactly {num_queries} specific search queries to find the best learning resources.\n"
        "Return ONLY a valid JSON array of strings, no other text. "
        'Example: ["query 1", "query 2"]'
    )
    user_message = f"Topic: {topic}\nDifficulty: {difficulty}"

    def _call_groq() -> str:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        return response.choices[0].message.content

    try:
        raw_content = await asyncio.to_thread(_call_groq)
        logger.info("Groq response for generate_search_queries: %s", raw_content)

        # Strip markdown code fences if present
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        queries = json.loads(cleaned)

        if not isinstance(queries, list):
            raise ValueError(f"Expected a JSON array, got: {type(queries)}")

        # Ensure all elements are strings
        queries = [str(q) for q in queries]
        logger.info("Generated %d search queries for topic '%s'.", len(queries), topic)
        return queries

    except Exception as e:
        logger.error(
            "Failed to generate search queries via Groq for topic '%s': %s. "
            "Falling back to basic queries.",
            topic,
            e,
        )
        return [
            f"{topic} tutorial",
            f"learn {topic}",
            f"{topic} for {difficulty.lower()}s",
            f"{topic} getting started guide",
            f"best resources to learn {topic}",
        ][:num_queries]


async def parse_learning_intent(topic: str) -> dict:
    """
    Use Groq to decompose a learning topic into subtopics and a recommended difficulty.

    Args:
        topic: The subject the user wants to learn.

    Returns:
        A dict with keys:
            - "topic" (str): the original topic
            - "subtopics" (list[str]): 3-5 subtopic strings
            - "recommended_difficulty" (str): e.g. "Beginner"
        Falls back to a sensible default dict on any failure.
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

    def _call_groq() -> str:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            max_tokens=512,
        )
        return response.choices[0].message.content

    try:
        raw_content = await asyncio.to_thread(_call_groq)
        logger.info("Groq response for parse_learning_intent: %s", raw_content)

        # Strip markdown code fences if present
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        result = json.loads(cleaned)

        if not isinstance(result, dict):
            raise ValueError(f"Expected a JSON object, got: {type(result)}")

        # Validate and coerce expected fields
        parsed = {
            "topic": str(result.get("topic", topic)),
            "subtopics": [str(s) for s in result.get("subtopics", [])],
            "recommended_difficulty": str(
                result.get("recommended_difficulty", "Beginner")
            ),
        }

        if not parsed["subtopics"]:
            raise ValueError("Groq returned empty subtopics list.")

        logger.info(
            "Parsed learning intent for topic '%s': %d subtopics, difficulty='%s'.",
            topic,
            len(parsed["subtopics"]),
            parsed["recommended_difficulty"],
        )
        return parsed

    except Exception as e:
        logger.error(
            "Failed to parse learning intent via Groq for topic '%s': %s. "
            "Returning default dict.",
            topic,
            e,
        )
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
        print(f"Topic: {test_topic!r}, Difficulty: {test_difficulty!r}")
        queries = await generate_search_queries(
            topic=test_topic, difficulty=test_difficulty
        )
        print("Search queries:")
        for i, q in enumerate(queries, start=1):
            print(f"  {i}. {q}")

        print(f"\n--- Testing parse_learning_intent ---")
        print(f"Topic: {test_topic!r}")
        intent = await parse_learning_intent(topic=test_topic)
        print("Parsed intent:")
        print(f"  Topic:                 {intent['topic']}")
        print(f"  Recommended Difficulty:{intent['recommended_difficulty']}")
        print(f"  Subtopics:")
        for i, s in enumerate(intent["subtopics"], start=1):
            print(f"    {i}. {s}")

    asyncio.run(main())
