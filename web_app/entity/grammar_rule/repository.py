"""
entity/grammar_rule/repository.py
------------------------------------
All database queries for the `grammar_rule` table (plus its optional
`grammar_context` rows) using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, aliased

from entity.grammar_rule.entity import GrammarRule
from entity.grammar_context.entity import GrammarContext


class GrammarRuleRepository:
    """Encapsulates all CRUD operations for the GrammarRule entity."""

    # Columns a caller is allowed to set on create / update.
    WRITABLE_FIELDS = {
        "grammar_id", "type", "passage_number", "vietnamese_content", "english_content",
    }

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

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        grammar_id: Optional[str] = None,
        type_: Optional[int] = None,
    ) -> tuple[list[GrammarRule], int]:
        """
        Return a paginated list of grammar rules and the total count.

        Optional filters: exact `grammar_id` match and `type_`.

        Returns:
            (items, total_count)
        """
        query = self.session.query(GrammarRule)
        if grammar_id:
            query = query.filter(GrammarRule.grammar_id == grammar_id)
        if type_ is not None:
            query = query.filter(GrammarRule.type == type_)

        total = query.count()
        items = (
            query.order_by(GrammarRule.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, rule_id: int) -> Optional[GrammarRule]:
        """Return a single GrammarRule by primary key, or None."""
        return self.session.get(GrammarRule, rule_id)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> GrammarRule:
        """
        Insert a new grammar rule. Only WRITABLE_FIELDS present in `data`
        are used.
        """
        values = {k: data[k] for k in self.WRITABLE_FIELDS if k in data}
        rule = GrammarRule(**values)
        self.session.add(rule)
        self.session.flush()  # flush to get the auto-generated id
        return rule

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, rule_id: int, data: dict) -> Optional[GrammarRule]:
        """
        Update allowed fields on an existing grammar rule.

        Only keys present in `data` (and in WRITABLE_FIELDS) are changed.

        Returns:
            The updated GrammarRule, or None if not found.
        """
        rule = self.get_by_id(rule_id)
        if not rule:
            return None

        for field in self.WRITABLE_FIELDS:
            if field in data:
                setattr(rule, field, data[field])

        self.session.flush()
        return rule

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, rule_id: int) -> bool:
        """
        Delete a grammar rule by ID.

        Returns:
            True if deleted, False if not found.
        """
        rule = self.get_by_id(rule_id)
        if not rule:
            return False
        self.session.delete(rule)
        self.session.flush()
        return True
