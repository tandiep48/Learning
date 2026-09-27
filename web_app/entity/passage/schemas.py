"""
entity/passage/schemas.py
-------------------------
Pydantic v2 request model for POST /api/admin/passage/query.
"""

from __future__ import annotations

from entity.query_schemas import HskLevel, PaginatedQuery


class PassageQuery(PaginatedQuery):
    """Validated filter + pagination for listing lesson passages."""

    hsk_level: HskLevel = None
