"""
repository/vocab_repository.py
--------------------------------
All database operations for the `vocabulary` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from typing import Optional
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from entity.vocabulary.entity import Vocabulary


class VocabRepository:
    """Encapsulates all CRUD operations for the Vocabulary entity."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        hsk_level: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Vocabulary], int]:
        """
        Return a paginated list of vocabulary entries and the total count.

        Args:
            page:      1-indexed page number.
            page_size: Number of items per page (max 100).
            hsk_level: Optional filter (e.g. "HSK1").
            search:    Optional case-insensitive match on the `cn` (Chinese word)
                       or `pinyin` columns.

        Returns:
            (items, total_count)
        """
        query = self.session.query(Vocabulary)
        if hsk_level:
            query = query.filter(Vocabulary.hsk_level == hsk_level)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                Vocabulary.cn.ilike(pattern) | Vocabulary.pinyin.ilike(pattern)
            )

        total = query.count()
        items = (
            query.order_by(Vocabulary.hsk_level, Vocabulary.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, vocab_id: int) -> Optional[Vocabulary]:
        """Return a single Vocabulary by primary key, or None."""
        return self.session.get(Vocabulary, vocab_id)

    def get_by_cn(self, cn: str) -> Optional[Vocabulary]:
        """Return a single Vocabulary by Chinese word (unique), or None."""
        return (
            self.session.query(Vocabulary)
            .filter(Vocabulary.cn == cn)
            .first()
        )

    def get_all_ordered(self) -> list[Vocabulary]:
        """Every vocabulary row, ordered by hsk_level then id."""
        return (
            self.session.query(Vocabulary)
            .order_by(Vocabulary.hsk_level, Vocabulary.id)
            .all()
        )

    def get_words_by_hsk_level(self, hsk_level: str) -> list[str]:
        """Chinese words for one HSK level, ordered by id."""
        rows = self.session.execute(
            select(Vocabulary.cn).where(Vocabulary.hsk_level == hsk_level).order_by(Vocabulary.id)
        ).all()
        return [r[0] for r in rows]

    def get_distinct_vn_meanings(self) -> list[str]:
        """Every distinct, non-empty Vietnamese meaning."""
        rows = self.session.execute(
            select(distinct(Vocabulary.meaning_vn)).where(
                Vocabulary.meaning_vn.isnot(None), Vocabulary.meaning_vn != ""
            )
        ).all()
        return [r[0] for r in rows]

    def get_by_words(self, words: list[str]) -> list[Vocabulary]:
        """Vocabulary rows whose `cn` is in `words`."""
        if not words:
            return []
        return self.session.execute(
            select(Vocabulary).where(Vocabulary.cn.in_(words))
        ).scalars().all()

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> Vocabulary:
        """
        Insert a new vocabulary entry.

        Args:
            data: Dict with keys matching Vocabulary columns.
                  Required: "cn".

        Returns:
            The newly created Vocabulary instance (after flush).

        Raises:
            IntegrityError: if `cn` already exists.
        """
        vocab = Vocabulary(
            cn=data["cn"],
            pinyin=data.get("pinyin"),
            meaning_en=data.get("meaning_en"),
            meaning_vn=data.get("meaning_vn"),
            audio_key=data.get("audio_key"),
            hsk_level=data.get("hsk_level"),
            source=data.get("source"),
        )
        self.session.add(vocab)
        self.session.flush()  # flush to get the auto-generated id
        return vocab

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, vocab_id: int, data: dict) -> Optional[Vocabulary]:
        """
        Update allowed fields on an existing vocabulary entry.

        Args:
            vocab_id: Primary key of the entry to update.
            data:     Dict of fields to update (only provided keys are changed).

        Returns:
            The updated Vocabulary, or None if not found.
        """
        vocab = self.get_by_id(vocab_id)
        if not vocab:
            return None

        updatable_fields = {
            "cn", "pinyin", "meaning_en", "meaning_vn",
            "audio_key", "hsk_level", "source",
        }
        for field in updatable_fields:
            if field in data:
                setattr(vocab, field, data[field])

        self.session.flush()
        return vocab

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, vocab_id: int) -> bool:
        """
        Delete a vocabulary entry by ID.

        Returns:
            True if deleted, False if not found.
        """
        vocab = self.get_by_id(vocab_id)
        if not vocab:
            return False
        self.session.delete(vocab)
        self.session.flush()
        return True
