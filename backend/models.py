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
    lesson_context: str = Field(
        description=(
            "1-2 sentences describing EXACTLY what this lesson covers and how it connects to "
            "the previous lesson. Written by the curriculum planner to ensure continuity and "
            "prevent content drift during downstream JIT generation."
        )
    )
    target_search_queries: list[str] = Field(
        description=(
            "1-2 highly specific web search queries that should be executed when generating "
            "the full content for this lesson. Act as a search architect: queries must be "
            "precise enough that the top results contain exactly the information needed for "
            "this lesson's scope."
        )
    )


class OutlineModule(BaseModel):
    module_title: str = Field(description="Title of the module, e.g. 'Module 1: Foundations'")
    lessons: list[OutlineLesson] = Field(description="Ordered list of lessons in this module")


class CourseOutline(BaseModel):
    course_title: str = Field(description="Full title of the course")
    difficulty_level: Literal["Beginner", "Intermediate", "Advanced"] = Field(
        description="Target audience difficulty level"
    )
    estimated_hours: float = Field(description="Estimated total learning hours")
    modules: list[OutlineModule] = Field(description="Ordered list of modules, each building on the previous")


# ---------------------------------------------------------------------------
# Lesson Detail — rich interactive payload returned by /api/generate-lesson
# Generated on-demand per lesson click.
# estimated_time_minutes is calculated programmatically — NOT by the LLM.
# ---------------------------------------------------------------------------

class LessonSection(BaseModel):
    section_title: str = Field(
        description=(
            "A clear, specific heading for this section of the lesson. "
            "E.g. 'What is the DOM Tree?', 'Event Bubbling Explained', 'Common Pitfalls'."
        )
    )
    explanation: str = Field(
        description=(
            "A detailed explanation of this section's concept. Use markdown formatting: "
            "**bold** for key terms, bullet points for lists, and clear paragraph breaks. "
            "Write 1-3 paragraphs (not a single sentence). Be thorough and educational."
        )
    )
    code_snippet: Optional[str] = Field(
        default=None,
        description=(
            "A concrete code example or command demonstrating this section's concept. "
            "Use a fenced markdown code block with a language tag, e.g. ```python. "
            "Null if no code is relevant to this section."
        ),
    )
    visual_analogy: Optional[str] = Field(
        default=None,
        description=(
            "A single sentence real-world analogy to make the concept intuitive. "
            "E.g. 'Think of the DOM like a family tree where each HTML element is a family member.' "
            "Null if no clear analogy exists."
        ),
    )


class Exercise(BaseModel):
    question: str = Field(description="A clear, specific multiple-choice question")
    options: list[str] = Field(description="Between 2 and 4 answer options as plain strings")
    correct_answer: str = Field(description="Must exactly match one of the options strings")
    explanation: str = Field(description="A 1-2 sentence explanation of why the answer is correct")


class LessonSource(BaseModel):
    title: str = Field(description="Title of the source article or page")
    url: str = Field(description="URL of the source")
    snippet: str = Field(default="", description="Short excerpt from the source")


class LessonDetail(BaseModel):
    lesson_id: str = Field(description="UUID matching the outline's lesson_id")
    lesson_title: str = Field(description="Lesson title (same as outline)")
    estimated_time_minutes: int = Field(
        description="Calculated programmatically from word count — do not hallucinate this value",
        default=5,
    )
    video_url: Optional[str] = Field(
        default=None,
        description="A real, highly relevant YouTube URL for this topic. Null if none found.",
    )
    sections: list[LessonSection] = Field(
        description=(
            "3-5 distinct content sections that together form a complete, deep lesson. "
            "Each section covers a different aspect or sub-concept of the lesson topic. "
            "Do NOT write a single monolithic block — chunk the content into clearly titled sections."
        )
    )
    exercises: list[Exercise] = Field(
        description="2-3 multiple-choice questions for active recall practice"
    )
    key_takeaways: list[str] = Field(
        description="3-5 bullet points summarizing the most important things to remember"
    )
    sources: list[LessonSource] = Field(
        default_factory=list,
        description="Source articles used to generate this lesson, for further reading"
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
    lesson_context: str = Field(description="1-2 sentence curriculum context from the outline")
    target_search_queries: list[str] = Field(description="Pre-planned search queries from the outline")
    course_title: str = Field(description="Parent course title for context")
    difficulty: Literal["Beginner", "Intermediate", "Advanced"] = "Beginner"
