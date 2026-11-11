from __future__ import annotations

from pydantic import BaseModel, Field


class QAItem(BaseModel):
    """A single question-and-answer pair in a study guide."""

    question: str = Field(..., min_length=1, description="The study guide question.")
    answer: str = Field(
        ...,
        min_length=1,
        description="The detailed answer grounded in the source text.",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="Optional 1-based page reference where the concept was extracted from.",
    )
