"""
entity/question/schemas.py
--------------------------
Pydantic v2 request model for POST /api/admin/question/query.
"""

from __future__ import annotations

from entity.query_schemas import PaginatedQuery, trimmed_str

Str20 = trimmed_str(20)
Str50 = trimmed_str(50)
Str100 = trimmed_str(100)


class QuestionQuery(PaginatedQuery):
    """Validated filters + pagination for listing questions."""

    category: Str50 = None
    level: Str20 = None
    lesson: Str50 = None
    skill: Str50 = None
    search: Str100 = None
