"""
service/passage_service.py
----------------------------
Business logic and validation for the Passage (lesson_passages + lesson_lines)
CRUD API.

Responsibilities:
  - Validate required fields (passage_id, passage_id format).
  - Guard against duplicate passage_id on create.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError

from entity.database import SessionLocal
from repository.passage_repository import PassageRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class PassageServiceError(Exception):
    """Raised for business-rule violations (400/404-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


_PASSAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")


def _validate_passage_id(passage_id: str) -> str:
    pid = (passage_id or "").strip()
    if not pid:
        raise PassageServiceError("Field 'passage_id' is required.")
    if not _PASSAGE_ID_PATTERN.match(pid):
        raise PassageServiceError(
            "Field 'passage_id' may only contain letters, digits, underscores, and hyphens."
        )
    return pid


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, 100))


def _clamp_page(page: int) -> int:
    return max(1, page)


def _validate_line(line: dict, index: int) -> None:
    """Light validation on a single line dict."""
    if not isinstance(line, dict):
        raise PassageServiceError(f"lines[{index}] must be an object.")
    if line.get("tokens") is not None and not isinstance(line["tokens"], list):
        raise PassageServiceError(f"lines[{index}].tokens must be a list or null.")


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def list_passages(
    page: int = 1,
    page_size: int = 20,
    hsk_level: str | None = None,
) -> dict:
    """
    Return a paginated list of passages (without lines).

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
        repo = PassageRepository(session)
        items, total = repo.get_all(page=page, page_size=page_size, hsk_level=hsk_level or None)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": [p.to_dict(include_lines=False) for p in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    finally:
        SessionLocal.remove()


def get_passage(passage_id: str) -> dict:
    """
    Return a single passage with its lines.

    Raises:
        PassageServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        passage = repo.get_by_id(passage_id)
        if not passage:
            raise PassageServiceError(
                f"Passage '{passage_id}' not found.", 404
            )
        return passage.to_dict(include_lines=True)
    finally:
        SessionLocal.remove()


def create_passage(data: dict) -> dict:
    """
    Create a new passage (and optionally its lines).

    Required fields: "passage_id"
    Optional fields: "hsk_level", "lines" (list of line objects)

    Line object fields (all optional):
        line_id, speaker, content, pinyin, audio_key,
        translation_en, translation_vi, tokens (list)

    Raises:
        PassageServiceError(400): validation failure or duplicate.
    """
    pid = _validate_passage_id(data.get("passage_id", ""))
    data["passage_id"] = pid

    lines = data.get("lines", [])
    if not isinstance(lines, list):
        raise PassageServiceError("Field 'lines' must be an array.")
    for i, line in enumerate(lines):
        _validate_line(line, i)

    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        if repo.get_by_id(pid):
            raise PassageServiceError(
                f"Passage '{pid}' already exists. Use PUT to update it."
            )

        passage = repo.create(data)
        session.commit()
        return passage.to_dict(include_lines=True)
    except PassageServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise PassageServiceError(f"Passage '{pid}' already exists.")
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_passage(passage_id: str, data: dict) -> dict:
    """
    Update an existing passage.

    Allowed fields: "hsk_level", "lines"
    If "lines" is included, all existing lines are replaced.

    Raises:
        PassageServiceError(404): if not found.
        PassageServiceError(400): if validation fails.
    """
    if not data:
        raise PassageServiceError("No fields provided to update.")

    lines = data.get("lines")
    if lines is not None:
        if not isinstance(lines, list):
            raise PassageServiceError("Field 'lines' must be an array.")
        for i, line in enumerate(lines):
            _validate_line(line, i)

    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        passage = repo.update(passage_id, data)
        if not passage:
            raise PassageServiceError(f"Passage '{passage_id}' not found.", 404)
        session.commit()
        return passage.to_dict(include_lines=True)
    except PassageServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def delete_passage(passage_id: str) -> dict:
    """
    Delete a passage and all its lines (via cascade).

    Raises:
        PassageServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        deleted = repo.delete(passage_id)
        if not deleted:
            raise PassageServiceError(f"Passage '{passage_id}' not found.", 404)
        session.commit()
        return {"message": f"Passage '{passage_id}' and all its lines deleted successfully."}
    except PassageServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
