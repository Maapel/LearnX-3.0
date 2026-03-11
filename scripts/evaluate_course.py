#!/usr/bin/env python3
"""
evaluate_course.py — LearnX 3.0 Course Quality Evaluator
=========================================================
1. Calls /api/generate-outline  → gets course skeleton
2. For each lesson: calls /api/generate-lesson → gets rich content
3. Sends each lesson to Groq (as a subject-matter expert) for critique
4. Saves a full Markdown report to reports/evaluation_<topic>_<timestamp>.md

Usage:
    python scripts/evaluate_course.py --topic "Machine Learning" --difficulty Intermediate
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from groq import Groq

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.2")
BACKEND_URL     = os.getenv("BACKEND_URL", "http://localhost:8000")
REPORTS_DIR     = Path(__file__).resolve().parents[1] / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

EXPERT_SYSTEM = """\
You are a world-class subject-matter expert and senior curriculum reviewer.
You will be given the content of a single educational lesson.
Evaluate it rigorously across these dimensions:

1. **Accuracy** — Are facts, definitions, and code examples correct? Flag any errors.
2. **Depth** — Is the coverage deep enough for the stated difficulty level?
3. **Clarity** — Are explanations clear, well-structured, and jargon-free where needed?
4. **Pedagogical Quality** — Do the sections build logically? Are exercises meaningful?
5. **Code Quality** — If code is present, is it idiomatic, runnable, and well-explained?

Output ONLY a JSON object with this structure:
{
  "overall_score": <1-10 integer>,
  "accuracy_score": <1-10>,
  "depth_score": <1-10>,
  "clarity_score": <1-10>,
  "pedagogy_score": <1-10>,
  "code_quality_score": <1-10 or null if no code>,
  "strengths": ["...", "..."],
  "issues": ["...", "..."],
  "suggestions": ["...", "..."],
  "verdict": "<one sentence summary>"
}
Return ONLY JSON."""

EXPERT_PROMPT = """\
Subject: {subject}
Difficulty: {difficulty}
Lesson: {lesson_title}

=== SECTIONS ===
{sections}

=== EXERCISES ===
{exercises}

=== KEY TAKEAWAYS ===
{takeaways}
"""


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── API calls ─────────────────────────────────────────────────────────────────

def generate_outline(topic: str, difficulty: str) -> dict:
    log(f"Generating outline: {topic!r} ({difficulty})")
    r = httpx.post(
        f"{BACKEND_URL}/api/generate-outline",
        json={"topic": topic, "difficulty": difficulty},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def generate_lesson(lesson: dict, course_title: str, difficulty: str) -> dict:
    log(f"  Generating lesson: {lesson['lesson_title']!r}")
    r = httpx.post(
        f"{BACKEND_URL}/api/generate-lesson",
        json={
            "lesson_id":             lesson["lesson_id"],
            "lesson_title":          lesson["lesson_title"],
            "lesson_context":        lesson["lesson_context"],
            "target_search_queries": lesson["target_search_queries"],
            "course_title":          course_title,
            "difficulty":            difficulty,
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()


# ── Expert evaluation ─────────────────────────────────────────────────────────

def _parse_eval_response(raw: str) -> dict:
    """Strip fences and parse JSON from an LLM eval response."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(l for l in lines if not l.strip().startswith("```"))
    # Find first { ... }
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        raw = raw[start:end + 1]
    return json.loads(raw)


def _call_groq_eval(prompt: str) -> str:
    groq = Groq(api_key=GROQ_API_KEY)
    delays = [10, 30]
    for attempt in range(3):
        try:
            resp = groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": EXPERT_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            if "429" in str(exc) and attempt < 2:
                log(f"    Groq rate limited — waiting {delays[attempt]}s...")
                time.sleep(delays[attempt])
            else:
                raise


def _call_ollama_eval(prompt: str) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": EXPERT_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }
    with httpx.Client(timeout=300.0) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"]


def evaluate_lesson(lesson_data: dict, course_title: str, difficulty: str) -> dict:
    """Evaluate lesson via Groq → Ollama cascade. Returns parsed score dict."""
    sections_txt = ""
    for i, s in enumerate(lesson_data.get("sections", []), 1):
        sections_txt += f"\n--- Section {i}: {s['section_title']} ---\n"
        sections_txt += s.get("explanation", "") + "\n"
        if s.get("code_snippet"):
            sections_txt += f"Code:\n{s['code_snippet']}\n"
        if s.get("visual_analogy"):
            sections_txt += f"Analogy: {s['visual_analogy']}\n"

    exercises_txt = ""
    for i, ex in enumerate(lesson_data.get("exercises", []), 1):
        exercises_txt += f"\nQ{i}: {ex['question']}\n"
        for opt in ex.get("options", []):
            mark = "✓" if opt == ex.get("correct_answer") else " "
            exercises_txt += f"  [{mark}] {opt}\n"
        exercises_txt += f"Explanation: {ex.get('explanation', '')}\n"

    takeaways_txt = "\n".join(f"• {t}" for t in lesson_data.get("key_takeaways", []))

    prompt = EXPERT_PROMPT.format(
        subject=course_title,
        difficulty=difficulty,
        lesson_title=lesson_data["lesson_title"],
        sections=sections_txt.strip(),
        exercises=exercises_txt.strip(),
        takeaways=takeaways_txt,
    )

    # Try Groq first
    if GROQ_API_KEY:
        try:
            raw = _call_groq_eval(prompt)
            log(f"    Evaluated via Groq")
            return _parse_eval_response(raw)
        except Exception as exc:
            log(f"    Groq eval failed ({exc}) — falling back to Ollama")

    # Fallback: Ollama
    try:
        raw = _call_ollama_eval(prompt)
        log(f"    Evaluated via Ollama")
        return _parse_eval_response(raw)
    except Exception as exc:
        log(f"    Ollama eval also failed: {exc}")
        return {"error": str(exc), "overall_score": None}


# ── Report rendering ──────────────────────────────────────────────────────────

def score_bar(score: int | None, max_score: int = 10) -> str:
    if score is None:
        return "N/A"
    filled = round((score / max_score) * 10)
    return "█" * filled + "░" * (10 - filled) + f"  {score}/{max_score}"


def render_report(topic: str, difficulty: str, outline: dict,
                  lesson_results: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    course_title = outline.get("course_title", topic)

    # Aggregate scores
    scored = [r for r in lesson_results if r.get("eval") and r["eval"].get("overall_score")]
    avg_overall   = round(sum(r["eval"]["overall_score"]   for r in scored) / len(scored), 1) if scored else 0
    avg_accuracy  = round(sum(r["eval"].get("accuracy_score",  0) for r in scored) / len(scored), 1) if scored else 0
    avg_depth     = round(sum(r["eval"].get("depth_score",     0) for r in scored) / len(scored), 1) if scored else 0
    avg_clarity   = round(sum(r["eval"].get("clarity_score",   0) for r in scored) / len(scored), 1) if scored else 0
    avg_pedagogy  = round(sum(r["eval"].get("pedagogy_score",  0) for r in scored) / len(scored), 1) if scored else 0

    lines = [
        f"# LearnX Course Evaluation Report",
        f"",
        f"**Course:** {course_title}",
        f"**Difficulty:** {difficulty}",
        f"**Generated:** {now}",
        f"**Lessons evaluated:** {len(scored)} / {len(lesson_results)}",
        f"",
        f"---",
        f"",
        f"## Overall Scores",
        f"",
        f"| Dimension      | Score | Bar |",
        f"|----------------|-------|-----|",
        f"| Overall        | {avg_overall}/10 | {score_bar(avg_overall)} |",
        f"| Accuracy       | {avg_accuracy}/10 | {score_bar(avg_accuracy)} |",
        f"| Depth          | {avg_depth}/10 | {score_bar(avg_depth)} |",
        f"| Clarity        | {avg_clarity}/10 | {score_bar(avg_clarity)} |",
        f"| Pedagogy       | {avg_pedagogy}/10 | {score_bar(avg_pedagogy)} |",
        f"",
        f"---",
        f"",
    ]

    for mod_idx, mod in enumerate(outline.get("modules", []), 1):
        lines.append(f"## {mod['module_title']}")
        lines.append("")

        for lesson in mod.get("lessons", []):
            result = next((r for r in lesson_results if r["lesson_id"] == lesson["lesson_id"]), None)
            if not result:
                lines.append(f"### {lesson['lesson_title']}  _(skipped)_")
                lines.append("")
                continue

            ev = result.get("eval", {})
            overall = ev.get("overall_score")
            verdict = ev.get("verdict", "")

            lines.append(f"### {lesson['lesson_title']}")
            lines.append("")

            if ev.get("error"):
                lines.append(f"> ⚠️ Evaluation failed: {ev['error']}")
                lines.append("")
                continue

            lines.append(f"**Overall:** {score_bar(overall)}")
            lines.append("")
            lines.append(f"| Dimension | Score |")
            lines.append(f"|-----------|-------|")
            lines.append(f"| Accuracy  | {ev.get('accuracy_score', 'N/A')}/10 |")
            lines.append(f"| Depth     | {ev.get('depth_score', 'N/A')}/10 |")
            lines.append(f"| Clarity   | {ev.get('clarity_score', 'N/A')}/10 |")
            lines.append(f"| Pedagogy  | {ev.get('pedagogy_score', 'N/A')}/10 |")
            if ev.get("code_quality_score") is not None:
                lines.append(f"| Code Quality | {ev.get('code_quality_score')}/10 |")
            lines.append("")

            if verdict:
                lines.append(f"**Verdict:** {verdict}")
                lines.append("")

            if ev.get("strengths"):
                lines.append("**Strengths:**")
                for s in ev["strengths"]:
                    lines.append(f"- {s}")
                lines.append("")

            if ev.get("issues"):
                lines.append("**Issues:**")
                for s in ev["issues"]:
                    lines.append(f"- {s}")
                lines.append("")

            if ev.get("suggestions"):
                lines.append("**Suggestions:**")
                for s in ev["suggestions"]:
                    lines.append(f"- {s}")
                lines.append("")

            lines.append("---")
            lines.append("")

    lines.append("## Raw Lesson Data")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps([
        {
            "lesson_title": r["lesson_title"],
            "sections": len(r.get("lesson_data", {}).get("sections", [])),
            "exercises": len(r.get("lesson_data", {}).get("exercises", [])),
            "key_takeaways": len(r.get("lesson_data", {}).get("key_takeaways", [])),
            "estimated_time_minutes": r.get("lesson_data", {}).get("estimated_time_minutes"),
            "eval": r.get("eval", {}),
        }
        for r in lesson_results
    ], indent=2))
    lines.append("```")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LearnX Course Evaluator")
    parser.add_argument("--topic",      default="Machine Learning",  help="Course topic")
    parser.add_argument("--difficulty", default="Intermediate",      choices=["Beginner", "Intermediate", "Advanced"])
    args = parser.parse_args()

    topic      = args.topic
    difficulty = args.difficulty

    # 1. Generate outline
    outline = generate_outline(topic, difficulty)
    course_title = outline.get("course_title", topic)
    modules = outline.get("modules", [])
    log(f"Outline ready: {course_title!r} — {len(modules)} modules")

    # 2. Generate every lesson + evaluate
    lesson_results: list[dict] = []

    for mod_idx, mod in enumerate(modules, 1):
        log(f"\nModule {mod_idx}: {mod['module_title']}")
        for lesson in mod.get("lessons", []):
            try:
                lesson_data = generate_lesson(lesson, course_title, difficulty)
            except Exception as exc:
                log(f"    Lesson generation failed: {exc}")
                lesson_results.append({
                    "lesson_id":    lesson["lesson_id"],
                    "lesson_title": lesson["lesson_title"],
                    "lesson_data":  {},
                    "eval":         {"error": str(exc)},
                })
                continue

            log(f"    Evaluating with subject-matter expert...")
            ev = evaluate_lesson(lesson_data, course_title, difficulty)

            lesson_results.append({
                "lesson_id":    lesson["lesson_id"],
                "lesson_title": lesson["lesson_title"],
                "lesson_data":  lesson_data,
                "eval":         ev,
            })

            # Avoid Groq rate limits between evaluations
            time.sleep(3)

    # 3. Render + save report
    report_md = render_report(topic, difficulty, outline, lesson_results)
    safe_topic = topic.replace(" ", "_").lower()[:30]
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path   = REPORTS_DIR / f"evaluation_{safe_topic}_{timestamp}.md"
    out_path.write_text(report_md, encoding="utf-8")
    log(f"\nReport saved → {out_path}")
    print(report_md[:2000])  # preview first 2000 chars


if __name__ == "__main__":
    main()
