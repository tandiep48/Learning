"""
entity/grammar_rule/repository.py
------------------------------------
All database queries for the `grammar_rule` table (plus its optional
`grammar_context` rows) using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from sqlalchemy import select, and_
from sqlalchemy.orm import Session, aliased

from entity.grammar_rule.entity import GrammarRule
from entity.grammar_context.entity import GrammarContext


class GrammarRuleRepository:
    """Encapsulates all read operations for the GrammarRule entity."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_rules_for_lesson(self, pattern: str):
        """
        All grammar rules whose grammar_id matches the LIKE `pattern` (e.g.
        "H1-2-%", covering every part of the lesson), each row joined with
        its optional Vietnamese/English grammar_context, ordered by
        insertion id. The caller splits the flat list into sections at
        each type=1 row.
        """
        c_vn = aliased(GrammarContext)
        c_en = aliased(GrammarContext)
        return self.session.execute(
            select(
                GrammarRule.grammar_id,
                GrammarRule.type,
                GrammarRule.vietnamese_content,
                GrammarRule.english_content,
                c_vn.content_json.label("vn_context"),
                c_en.content_json.label("en_context"),
            )
            .select_from(GrammarRule)
            .outerjoin(c_vn, and_(GrammarRule.vietnamese_content == c_vn.grammar_id, GrammarRule.type == 4))
            .outerjoin(c_en, and_(GrammarRule.english_content == c_en.grammar_id, GrammarRule.type == 4))
            .where(GrammarRule.grammar_id.like(pattern))
            .order_by(GrammarRule.id.asc())
        ).all()
