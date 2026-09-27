"""
entity/grammar_rule/schemas.py
------------------------------
Pydantic v2 request model for POST /api/admin/grammar_rule/query.
"""

from __future__ import annotations

from typing import Optional

from entity.query_schemas import PaginatedQuery, trimmed_str

GrammarId = trimmed_str(50)


class GrammarRuleQuery(PaginatedQuery):
    """Validated filter + pagination for listing grammar rules."""

    grammar_id: GrammarId = None
    # Maps to the service's `type_` argument.
    type: Optional[int] = None
