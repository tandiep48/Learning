"""
service/vocab_service.py
--------------------------
Business logic and validation for the Vocabulary CRUD API.

Responsibilities:
  - Validate required/optional fields.
  - Guard against duplicate `cn` values on create.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from entity.database import SessionLocal
from repository.vocab_repository import VocabRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class VocabServiceError(Exception):
    """Raised for business-rule violations (400-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, 100))


def _clamp_page(page: int) -> int:
    return max(1, page)


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def list_vocab(
    page: int = 1,
    page_size: int = 20,
    hsk_level: str | None = None,
) -> dict:
    """
    Return a paginated list of vocabulary entries.

    Returns:
        {
            "items":       [...],
            "page":        int,
            "page_size":   int,
            "total":       int,
            "total_pages": int,
        }
    """
    page = _clamp_page(page)
    page_size = _clamp_page_size(page_size)

    session = SessionLocal()
    try:
        repo = VocabRepository(session)
        items, total = repo.get_all(page=page, page_size=page_size, hsk_level=hsk_level or None)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": [v.to_dict() for v in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    finally:
        SessionLocal.remove()


def get_vocab(vocab_id: int) -> dict:
    """
    Return a single vocabulary entry by ID.

    Raises:
        VocabServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = VocabRepository(session)
        vocab = repo.get_by_id(vocab_id)
        if not vocab:
            raise VocabServiceError(f"Vocabulary with id={vocab_id} not found.", 404)
        return vocab.to_dict()
    finally:
        SessionLocal.remove()


def create_vocab(data: dict) -> dict:
    """
    Create a new vocabulary entry.

    Required fields: "cn"

    Raises:
        VocabServiceError(400): if "cn" is missing or already exists.
    """
    cn = (data.get("cn") or "").strip()
    if not cn:
        raise VocabServiceError("Field 'cn' (Chinese word) is required.")

    session = SessionLocal()
    try:
        repo = VocabRepository(session)

        # Duplicate guard
        if repo.get_by_cn(cn):
            raise VocabServiceError(
                f"Vocabulary '{cn}' already exists. Use PUT to update it."
            )

        data["cn"] = cn
        vocab = repo.create(data)
        session.commit()
        return vocab.to_dict()
    except VocabServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise VocabServiceError(f"Vocabulary '{cn}' already exists.")
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_vocab(vocab_id: int, data: dict) -> dict:
    """
    Update an existing vocabulary entry.

    Raises:
        VocabServiceError(404): if not found.
        VocabServiceError(400): if the new `cn` value conflicts with another entry.
    """
    if not data:
        raise VocabServiceError("No fields provided to update.")

    # Strip cn if provided
    if "cn" in data:
        cn = (data["cn"] or "").strip()
        if not cn:
            raise VocabServiceError("Field 'cn' cannot be empty.")
        data["cn"] = cn

    session = SessionLocal()
    try:
        repo = VocabRepository(session)
        vocab = repo.update(vocab_id, data)
        if not vocab:
            raise VocabServiceError(f"Vocabulary with id={vocab_id} not found.", 404)
        session.commit()
        return vocab.to_dict()
    except VocabServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise VocabServiceError("A vocabulary entry with that 'cn' already exists.")
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def delete_vocab(vocab_id: int) -> dict:
    """
    Delete a vocabulary entry by ID.

    Raises:
        VocabServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = VocabRepository(session)
        deleted = repo.delete(vocab_id)
        if not deleted:
            raise VocabServiceError(f"Vocabulary with id={vocab_id} not found.", 404)
        session.commit()
        return {"message": f"Vocabulary id={vocab_id} deleted successfully."}
    except VocabServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
