from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class Lesson(BaseModel):
    model_config = {"extra": "forbid"}

    lesson_title: str
    content_type: Literal["video", "article", "concept_breakdown"]
    source_url: Optional[str] = None
    content_markdown: str
    key_takeaways: list[str]


class Module(BaseModel):
    model_config = {"extra": "forbid"}

    module_title: str
    module_description: str
    lessons: list[Lesson]


class Course(BaseModel):
    model_config = {"extra": "forbid"}

    course_title: str
    difficulty_level: Literal["Beginner", "Intermediate", "Advanced"]
    estimated_hours: float
    modules: list[Module]


class CourseGenerateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    topic: str
    difficulty: Optional[Literal["Beginner", "Intermediate", "Advanced"]] = None
