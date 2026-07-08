"""
repository/passage_vocabulary_repository.py
--------------------------------------------
All database operations for the `passage_vocabulary` join table using
SQLAlchemy.

A row links a passage to a vocabulary word (by its Chinese text `cn`).
Listing returns the full `Vocabulary` rows so callers get pinyin / meanings
without a second lookup.
"""

from sqlalchemy.orm import Session

from entity.passage_vocabulary_entity import PassageVocabulary
from entity.vocabulary_entity import Vocabulary


class PassageVocabularyRepository:
    """Encapsulates all operations on the passage ↔ vocabulary link table."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_vocab(self, passage_id: str) -> list[Vocabulary]:
        """
        Return every Vocabulary linked to the given passage, ordered by word.
        """
        return (
            self.session.query(Vocabulary)
            .join(PassageVocabulary, PassageVocabulary.cn == Vocabulary.cn)
            .filter(PassageVocabulary.passage_id == passage_id)
            .order_by(Vocabulary.cn)
            .all()
        )

    def exists(self, passage_id: str, cn: str) -> bool:
        """Return True if the (passage_id, cn) link already exists."""
        return (
            self.session.query(PassageVocabulary)
            .filter(
                PassageVocabulary.passage_id == passage_id,
                PassageVocabulary.cn == cn,
            )
            .first()
            is not None
        )

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def add(self, passage_id: str, cn: str) -> PassageVocabulary:
        """Insert a new (passage_id, cn) link and return it."""
        link = PassageVocabulary(passage_id=passage_id, cn=cn)
        self.session.add(link)
        self.session.flush()
        return link

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def remove(self, passage_id: str, cn: str) -> bool:
        """
        Delete a (passage_id, cn) link.

        Returns:
            True if a row was deleted, False if it did not exist.
        """
        deleted = (
            self.session.query(PassageVocabulary)
            .filter(
                PassageVocabulary.passage_id == passage_id,
                PassageVocabulary.cn == cn,
            )
            .delete(synchronize_session=False)
        )
        return deleted > 0
