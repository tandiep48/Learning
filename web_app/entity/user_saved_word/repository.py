"""
repository/user_saved_word_repository.py
-----------------------------------------
All database operations for the `user_saved_word` personal word list using
SQLAlchemy.

A row links a user + passage to a vocabulary word (by its Chinese text `cn`).
Listing returns the full `Vocabulary` rows so callers get pinyin / meanings
without a second lookup.
"""

from sqlalchemy.orm import Session

from entity.user_saved_word.entity import UserSavedWord
from entity.vocabulary.entity import Vocabulary


class UserSavedWordRepository:
    """Encapsulates all operations on the user ↔ passage ↔ vocabulary list."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_vocab(self, user_id: int, passage_id: str) -> list[Vocabulary]:
        """Return every Vocabulary the user saved for the passage, by word."""
        return (
            self.session.query(Vocabulary)
            .join(UserSavedWord, UserSavedWord.cn == Vocabulary.cn)
            .filter(
                UserSavedWord.user_id == user_id,
                UserSavedWord.passage_id == passage_id,
            )
            .order_by(Vocabulary.cn)
            .all()
        )

    def exists(self, user_id: int, passage_id: str, cn: str) -> bool:
        """Return True if the (user_id, passage_id, cn) row already exists."""
        return (
            self.session.query(UserSavedWord)
            .filter(
                UserSavedWord.user_id == user_id,
                UserSavedWord.passage_id == passage_id,
                UserSavedWord.cn == cn,
            )
            .first()
            is not None
        )

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def add(self, user_id: int, passage_id: str, cn: str) -> UserSavedWord:
        """Insert a new saved-word row and return it."""
        row = UserSavedWord(user_id=user_id, passage_id=passage_id, cn=cn)
        self.session.add(row)
        self.session.flush()
        return row

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def remove(self, user_id: int, passage_id: str, cn: str) -> bool:
        """
        Delete a saved-word row.

        Returns:
            True if a row was deleted, False if it did not exist.
        """
        deleted = (
            self.session.query(UserSavedWord)
            .filter(
                UserSavedWord.user_id == user_id,
                UserSavedWord.passage_id == passage_id,
                UserSavedWord.cn == cn,
            )
            .delete(synchronize_session=False)
        )
        return deleted > 0
