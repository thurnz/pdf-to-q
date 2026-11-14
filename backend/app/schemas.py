from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QAItem(BaseModel):
    """A single question-and-answer pair in a study guide."""

    question: str = Field(default="", description="The study guide question.")
    answer: str = Field(
        default="",
        description="The detailed answer grounded in the source text.",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="Optional 1-based page reference where the concept was extracted from.",
    )


class GenerationOptions(BaseModel):
    """User-configurable options for study guide generation."""

    num_questions: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Target number of questions to generate.",
    )
    difficulty: Literal["easy", "medium", "hard"] = Field(
        default="medium",
        description="Cognitive difficulty level: easy (recall), medium (explain), hard (apply/compare).",
    )
    detail: Literal["short", "detailed"] = Field(
        default="short",
        description="Answer detail: short (1-2 sentences) or detailed (3-5 sentences).",
    )


class QAGenerationResult(BaseModel):
    """Expected structured JSON response schema from the LLM provider."""

    questions: list[QAItem] = Field(
        default_factory=list,
        description="List of extracted study guide question-and-answer items.",
    )


class JobStatus(BaseModel):
    """Public representation of a processing job's status."""

    id: str = Field(..., description="Unique job identifier.")
    status: Literal["queued", "processing", "done", "failed"] = Field(
        ..., description="Current job lifecycle status."
    )
    progress: float = Field(
        ..., ge=0.0, le=1.0, description="Processing progress from 0.0 to 1.0."
    )
    error: str | None = Field(
        default=None, description="Human-readable error message if job failed."
    )
