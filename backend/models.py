from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Course Outline — lightweight structure returned by /api/generate-outline
# Generated fast (<5s), no content, just the skeleton
# ---------------------------------------------------------------------------

class OutlineLesson(BaseModel):
    lesson_id: str = Field(description="A unique UUID string identifying this lesson")
    lesson_title: str = Field(description="A concise, descriptive title for the lesson")


class OutlineModule(BaseModel):
    module_title: str = Field(description="Title of the module / chapter")
    lessons: list[OutlineLesson] = Field(description="Ordered list of lessons in this module")


class CourseOutline(BaseModel):
    course_title: str = Field(description="Full title of the course")
    difficulty_level: Literal["Beginner", "Intermediate", "Advanced"] = Field(
        description="Target audience difficulty level"
    )
    estimated_hours: float = Field(description="Estimated total learning hours")
    modules: list[OutlineModule] = Field(description="Ordered list of modules")


# ---------------------------------------------------------------------------
# Lesson Detail — rich interactive payload returned by /api/generate-lesson
# Generated on-demand per lesson click, includes exercises and examples
# ---------------------------------------------------------------------------

class Exercise(BaseModel):
    question: str = Field(description="A clear, specific multiple-choice question")
    options: list[str] = Field(
        description="Between 2 and 4 answer options as plain strings"
    )
    correct_answer: str = Field(
        description="Must exactly match one of the options strings"
    )
    explanation: str = Field(
        description="A 1-2 sentence explanation of why the answer is correct"
    )


class LessonDetail(BaseModel):
    lesson_id: str = Field(description="UUID matching the outline's lesson_id")
    lesson_title: str = Field(description="Lesson title (same as outline)")
    estimated_time_minutes: int = Field(
        description="Realistic reading + practice time in minutes"
    )
    video_url: Optional[str] = Field(
        default=None,
        description="A real, highly relevant YouTube URL for this topic. Null if none found.",
    )
    concept_summary: str = Field(
        description=(
            "STRICTLY 3-4 punchy sentences. No long paragraphs. "
            "Explain the core idea clearly so a beginner can grasp it instantly."
        )
    )
    practical_example: Optional[str] = Field(
        default=None,
        description=(
            "A concrete code snippet, formula, or real-world example illustrating the concept. "
            "Use markdown fenced code blocks for code. Null if not applicable."
        ),
    )
    exercises: list[Exercise] = Field(
        description="2-3 multiple-choice questions for active recall practice"
    )
    key_takeaways: list[str] = Field(
        description="3-5 bullet points summarizing the most important things to remember"
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class OutlineGenerateRequest(BaseModel):
    topic: str = Field(description="The subject the user wants to learn")
    difficulty: Optional[Literal["Beginner", "Intermediate", "Advanced"]] = None


class LessonGenerateRequest(BaseModel):
    lesson_id: str = Field(description="UUID of the lesson to generate")
    lesson_title: str = Field(description="Title of the lesson to generate")
    course_title: str = Field(description="Parent course title for context")
    difficulty: Literal["Beginner", "Intermediate", "Advanced"] = "Beginner"
