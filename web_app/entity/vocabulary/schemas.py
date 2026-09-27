"""
entity/vocabulary/schemas.py
----------------------------
Pydantic v2 request model for the Vocabulary list endpoint.

VocabQuery validates the JSON body of POST /api/admin/vocab/query — the read
that used to be a GET with page/page_size/hsk_level/search crammed into the URL.
Shared paging + field types live in entity/query_schemas.py.
"""

from __future__ import annotations

from entity.query_schemas import HskLevel, PaginatedQuery, trimmed_str

SearchStr = trimmed_str(100)


class VocabQuery(PaginatedQuery):
    """Validated filter + pagination for listing vocabulary."""

    hsk_level: HskLevel = None
    search: SearchStr = None
