"""
service/passage_vocabulary_service.py
--------------------------------------
Business logic and validation for the passage ↔ vocabulary link CRUD API.

Responsibilities:
  - Ensure the passage exists before listing / mutating its words.
  - Ensure the vocabulary word exists (FK requirement) before linking it.
  - Guard against duplicate links.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from entity.database import SessionLocal
from repository.passage_repository import PassageRepository
from repository.vocab_repository import VocabRepository
from repository.passage_vocabulary_repository import PassageVocabularyRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class PassageVocabularyServiceError(Exception):
    """Raised for business-rule violations (400/404/409-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _require_passage(session, passage_id: str) -> None:
    """Raise 404 if the passage does not exist."""
    if not PassageRepository(session).get_by_id(passage_id):
        raise PassageVocabularyServiceError(
            f"Passage '{passage_id}' not found.", 404
        )


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def list_passage_vocab(passage_id: str) -> dict:
    """
    Return every vocabulary word linked to a passage.

    Returns:
        { "passage_id": str, "items": [<vocab dict>, ...], "total": int }

    Raises:
        PassageVocabularyServiceError(404): if the passage does not exist.
    """
    session = SessionLocal()
    try:
        _require_passage(session, passage_id)
        repo = PassageVocabularyRepository(session)
        items = repo.list_vocab(passage_id)
        return {
            "passage_id": passage_id,
            "items": [v.to_dict() for v in items],
            "total": len(items),
        }
    finally:
        SessionLocal.remove()


def add_passage_vocab(passage_id: str, cn: str) -> dict:
    """
    Link an existing vocabulary word to a passage.

    Args:
        passage_id: Target passage.
        cn:         Chinese word — must already exist in `vocabulary`.

    Raises:
        PassageVocabularyServiceError(400): if `cn` is missing.
        PassageVocabularyServiceError(404): if the passage or word does not exist.
        PassageVocabularyServiceError(409): if the link already exists.
    """
    cn = (cn or "").strip()
    if not cn:
        raise PassageVocabularyServiceError("Field 'cn' (Chinese word) is required.")

    session = SessionLocal()
    try:
        _require_passage(session, passage_id)

        if not VocabRepository(session).get_by_cn(cn):
            raise PassageVocabularyServiceError(
                f"Vocabulary '{cn}' does not exist. Create the word first.", 404
            )

        repo = PassageVocabularyRepository(session)
        if repo.exists(passage_id, cn):
            raise PassageVocabularyServiceError(
                f"'{cn}' is already linked to passage '{passage_id}'.", 409
            )

        repo.add(passage_id, cn)
        session.commit()
        return {
            "message": f"'{cn}' linked to passage '{passage_id}'.",
            "passage_id": passage_id,
            "cn": cn,
        }
    except PassageVocabularyServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise PassageVocabularyServiceError(
            f"'{cn}' is already linked to passage '{passage_id}'.", 409
        )
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def remove_passage_vocab(passage_id: str, cn: str) -> dict:
    """
    Remove the link between a passage and a vocabulary word.

    Raises:
        PassageVocabularyServiceError(404): if the link does not exist.
    """
    cn = (cn or "").strip()
    session = SessionLocal()
    try:
        repo = PassageVocabularyRepository(session)
        removed = repo.remove(passage_id, cn)
        if not removed:
            raise PassageVocabularyServiceError(
                f"'{cn}' is not linked to passage '{passage_id}'.", 404
            )
        session.commit()
        return {"message": f"'{cn}' unlinked from passage '{passage_id}'."}
    except PassageVocabularyServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
