"""
service/user_saved_word_service.py
-----------------------------------
Business logic and validation for the personal word-list (user_saved_word) API.

Responsibilities:
  - Ensure the passage exists before listing / mutating its words.
  - Ensure the vocabulary word exists (FK requirement + known-words-only rule)
    before saving it.
  - Guard against duplicate rows.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from entity.database import SessionLocal
from entity.passage.repository import PassageRepository
from entity.vocabulary.repository import VocabRepository
from entity.user_saved_word.repository import UserSavedWordRepository


class UserSavedWordServiceError(Exception):
    """Raised for business-rule violations (400/404/409-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _require_passage(session, passage_id: str) -> None:
    """Raise 404 if the passage does not exist."""
    if not PassageRepository(session).get_by_id(passage_id):
        raise UserSavedWordServiceError(f"Passage '{passage_id}' not found.", 404)


def list_saved_vocab(user_id: int, passage_id: str) -> list[dict]:
    """Return the vocabulary rows a user saved for a passage (plain dicts)."""
    session = SessionLocal()
    try:
        items = UserSavedWordRepository(session).list_vocab(user_id, passage_id)
        return [v.to_dict() for v in items]
    finally:
        SessionLocal.remove()


def add_saved_word(user_id: int, passage_id: str, cn: str) -> dict:
    """
    Save a known vocabulary word to the user's personal list for a passage.

    Raises:
        UserSavedWordServiceError(400): if `cn` is missing.
        UserSavedWordServiceError(404): if the passage or word does not exist.
        UserSavedWordServiceError(409): if the word is already saved.
    """
    cn = (cn or "").strip()
    if not cn:
        raise UserSavedWordServiceError("Field 'cn' (Chinese word) is required.")

    session = SessionLocal()
    try:
        _require_passage(session, passage_id)

        if not VocabRepository(session).get_by_cn(cn):
            raise UserSavedWordServiceError(
                f"Vocabulary '{cn}' does not exist.", 404
            )

        repo = UserSavedWordRepository(session)
        if repo.exists(user_id, passage_id, cn):
            raise UserSavedWordServiceError(
                f"'{cn}' is already in your list.", 409
            )

        repo.add(user_id, passage_id, cn)
        session.commit()
        return {"message": f"'{cn}' saved.", "passage_id": passage_id, "cn": cn}
    except UserSavedWordServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise UserSavedWordServiceError(f"'{cn}' is already in your list.", 409)
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def remove_saved_word(user_id: int, passage_id: str, cn: str) -> dict:
    """
    Remove a word from the user's personal list for a passage.

    Raises:
        UserSavedWordServiceError(404): if the word is not in the list.
    """
    cn = (cn or "").strip()
    session = SessionLocal()
    try:
        repo = UserSavedWordRepository(session)
        removed = repo.remove(user_id, passage_id, cn)
        if not removed:
            raise UserSavedWordServiceError(f"'{cn}' is not in your list.", 404)
        session.commit()
        return {"message": f"'{cn}' removed."}
    except UserSavedWordServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
