"""
entity/passage/schemas.py
-------------------------
Pydantic v2 request model for POST /api/admin/passage/query.
"""

from __future__ import annotations

from entity.query_schemas import HskLevel, PaginatedQuery, trimmed_str


class PassageQuery(PaginatedQuery):
    """Validated filter + pagination for listing lesson passages."""

    hsk_level: HskLevel = None
    book_code: trimmed_str(20) = None
    q: trimmed_str(100) = None  # part of a passage_id, any case
