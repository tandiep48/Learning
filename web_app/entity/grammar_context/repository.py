"""
entity/grammar_context/repository.py
---------------------------------------
All database operations for the `grammar_context` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from typing import Optional
from sqlalchemy.orm import Session

from entity.grammar_context.entity import GrammarContext


class GrammarContextRepository:
    """Encapsulates all CRUD operations for the GrammarContext entity."""

    # Columns a caller is allowed to set on create / update.
    WRITABLE_FIELDS = {"grammar_id", "content_json"}

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        grammar_id: Optional[str] = None,
    ) -> tuple[list[GrammarContext], int]:
        """
        Return a paginated list of grammar contexts and the total count.

        Optional filter: exact `grammar_id` match.

        Returns:
            (items, total_count)
        """
        query = self.session.query(GrammarContext)
        if grammar_id:
            query = query.filter(GrammarContext.grammar_id == grammar_id)

        total = query.count()
        items = (
            query.order_by(GrammarContext.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, context_id: int) -> Optional[GrammarContext]:
        """Return a single GrammarContext by primary key, or None."""
        return self.session.get(GrammarContext, context_id)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> GrammarContext:
        """
        Insert a new grammar context. Only WRITABLE_FIELDS present in
        `data` are used.
        """
        values = {k: data[k] for k in self.WRITABLE_FIELDS if k in data}
        context = GrammarContext(**values)
        self.session.add(context)
        self.session.flush()  # flush to get the auto-generated id
        return context

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, context_id: int, data: dict) -> Optional[GrammarContext]:
        """
        Update allowed fields on an existing grammar context.

        Only keys present in `data` (and in WRITABLE_FIELDS) are changed.

        Returns:
            The updated GrammarContext, or None if not found.
        """
        context = self.get_by_id(context_id)
        if not context:
            return None

        for field in self.WRITABLE_FIELDS:
            if field in data:
                setattr(context, field, data[field])

        self.session.flush()
        return context

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, context_id: int) -> bool:
        """
        Delete a grammar context by ID.

        Returns:
            True if deleted, False if not found.
        """
        context = self.get_by_id(context_id)
        if not context:
            return False
        self.session.delete(context)
        self.session.flush()
        return True
