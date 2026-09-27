"""
entity/grammar_context/schemas.py
---------------------------------
Pydantic v2 request model for POST /api/admin/grammar_context/query.
"""

from __future__ import annotations

from entity.query_schemas import PaginatedQuery, trimmed_str

GrammarId = trimmed_str(50)


class GrammarContextQuery(PaginatedQuery):
    """Validated filter + pagination for listing grammar contexts."""

    grammar_id: GrammarId = None
