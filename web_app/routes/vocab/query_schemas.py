"""
routes/vocab/query_schemas.py
-----------------------------
Pydantic v2 request models for the learner vocab list/search reads that now
accept a validated JSON body via POST .../query, alongside the existing GET
(which the legacy Jinja pages still use). Success responses stay raw JSON to
match the frontend's legacyApiFetch.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import Field

from entity.query_schemas import LearnerListQuery, trimmed_str

Search = trimmed_str(100)
Short = trimmed_str(50)
HskRaw = trimmed_str(20)


class VocabSearchQuery(LearnerListQuery):
    """POST /api/vocab/search/query — word/pinyin/meaning search."""

    q: Search = None


class VocabReviewQuery(LearnerListQuery):
    """POST /api/vocab/review/query — the prioritized review list."""

    page_size: int = Field(default=100, ge=1, le=1000)


class VocabTableQuery(LearnerListQuery):
    """POST /api/vocab/table/query — the training-selection table."""

    mode: Literal["free", "standard", "book", "unlearn", "unsure"] = "free"
    hsk_level: HskRaw = None
    lesson: Short = None
    part: Short = None
    passages: List[str] = Field(default_factory=list, max_length=1000)
    book_code: Short = None
