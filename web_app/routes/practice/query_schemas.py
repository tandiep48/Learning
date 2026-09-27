"""
routes/practice/query_schemas.py
--------------------------------
Pydantic v2 request model for the practice-history read, exposed as
POST /api/practice/history/query alongside the existing GET.

The filter values (level "all"/1..6, category, sort) are kept permissive and
normalized in the shared helper, exactly as the GET always did — so the model
rejects only structurally bad input (unknown keys, a non-int/zero page) and
never a value the review UI legitimately sends.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from entity.query_schemas import trimmed_str

Filter = trimmed_str(20)


class PracticeHistoryQuery(BaseModel):
    """POST /api/practice/history/query — the review page's session list."""

    model_config = ConfigDict(extra="forbid")

    level: Filter = None
    category: Filter = None
    sort: Filter = None
    page: int = Field(default=1, ge=1)
