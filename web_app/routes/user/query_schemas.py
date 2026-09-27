"""
routes/user/query_schemas.py
----------------------------
Pydantic v2 request model for the learner "learned vocab" read, exposed as
POST /api/user/learned-vocab/query alongside the existing GET.
"""

from __future__ import annotations

from pydantic import Field

from entity.query_schemas import LearnerListQuery


class LearnedVocabQuery(LearnerListQuery):
    """POST /api/user/learned-vocab/query — the user's mastered words, recent first."""

    page_size: int = Field(default=24, ge=1, le=1000)
