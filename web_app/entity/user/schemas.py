"""
entity/user/schemas.py
----------------------
Pydantic v2 request model for POST /api/admin/user/query.
"""

from __future__ import annotations

from entity.query_schemas import PaginatedQuery, trimmed_str

SearchStr = trimmed_str(100)


class UserQuery(PaginatedQuery):
    """Validated search + pagination for listing users."""

    search: SearchStr = None
