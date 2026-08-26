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
from entity.passage.repository import PassageRepository
from entity.validation import optional_str, optional_int, optional_list, optional_one_of, require_int


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
HSK_LEVELS = {f"HSK{n}" for n in range(1, 7)}


def _validate_passage_id(passage_id) -> str:
    if passage_id is not None and not isinstance(passage_id, str):
        raise PassageServiceError("Field 'passage_id' must be a string.")
    pid = (passage_id or "").strip()
    if not pid:
        raise PassageServiceError("Field 'passage_id' is required.")
    if len(pid) > 100:
        raise PassageServiceError("Field 'passage_id' must be 100 characters or fewer.")
    if not _PASSAGE_ID_PATTERN.match(pid):
        raise PassageServiceError(
            "Field 'passage_id' may only contain letters, digits, underscores, and hyphens."
        )
    return pid


def _validate_hsk_level(data: dict) -> dict:
    payload: dict = {}
    if "hsk_level" in data:
        payload["hsk_level"] = optional_one_of(PassageServiceError, "hsk_level", data["hsk_level"], HSK_LEVELS)
    return payload


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, 100))


def _clamp_page(page: int) -> int:
    return max(1, page)


_LINE_STR_FIELDS = {
    "speaker": 50,
    "content": None,
    "pinyin": None,
    "audio_key": 100,
    "translation_en": None,
    "translation_vi": None,
}


def _validate_line(line: dict, index: int) -> dict:
    """Validate a single line dict (type + length matching lesson_lines columns)."""
    if not isinstance(line, dict):
        raise PassageServiceError(f"lines[{index}] must be an object.")

    clean: dict = dict(line)
    for field, max_len in _LINE_STR_FIELDS.items():
        if field in clean:
            clean[field] = optional_str(PassageServiceError, f"lines[{index}].{field}", clean[field], max_len)
    if "line_id" in clean:
        clean["line_id"] = optional_int(PassageServiceError, f"lines[{index}].line_id", clean["line_id"])
    if "tokens" in clean:
        clean["tokens"] = optional_list(PassageServiceError, f"lines[{index}].tokens", clean["tokens"])
    return clean


def _validate_line_id(line_id) -> int:
    """`line_id` is the caller-facing key for a single line within a passage."""
    if line_id is None:
        raise PassageServiceError("Field 'line_id' is required.")
    return require_int(PassageServiceError, "line_id", line_id)


def _require_passage(repo: PassageRepository, passage_id: str) -> None:
    if not repo.get_by_id(passage_id):
        raise PassageServiceError(f"Passage '{passage_id}' not found.", 404)


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
    payload = _validate_hsk_level(data)
    payload["passage_id"] = pid

    lines = data.get("lines", [])
    if not isinstance(lines, list):
        raise PassageServiceError("Field 'lines' must be an array.")
    payload["lines"] = [_validate_line(line, i) for i, line in enumerate(lines)]

    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        if repo.get_by_id(pid):
            raise PassageServiceError(
                f"Passage '{pid}' already exists. Use PUT to update it."
            )

        passage = repo.create(payload)
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

    payload = _validate_hsk_level(data)

    lines = data.get("lines")
    if lines is not None:
        if not isinstance(lines, list):
            raise PassageServiceError("Field 'lines' must be an array.")
        payload["lines"] = [_validate_line(line, i) for i, line in enumerate(lines)]

    if not payload:
        raise PassageServiceError("No updatable fields provided.")

    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        passage = repo.update(passage_id, payload)
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


# ---------------------------------------------------------------------------
# Content lookups (lesson picker / lesson player)
# ---------------------------------------------------------------------------

def get_passages_summary(hsk_level: str | None = None, lang: str = "en") -> list[dict]:
    """Return every passage's id, hsk_level, line_count and localized title."""
    session = SessionLocal()
    try:
        rows = PassageRepository(session).get_summary(hsk_level)
        return [
            {
                "passage_id": r[0],
                "hsk_level": r[1],
                "line_count": r[2],
                "title": (r[4] or r[3]) if lang == "vi" else (r[3] or r[4]),
            }
            for r in rows
        ]
    finally:
        SessionLocal.remove()


def get_passage_content(passage_id: str) -> dict | None:
    """
    Return a passage with its lines shaped for the lesson player, or None
    if the passage does not exist.
    """
    session = SessionLocal()
    try:
        passage = PassageRepository(session).get_by_id(passage_id)
        if not passage:
            return None
        lines = [
            {
                "line_id": line.line_id,
                "speaker": line.speaker,
                "content": line.content,
                "pinyin": line.pinyin,
                "audio_key": line.audio_key,
                "translations": {"en": line.translation_en, "vi": line.translation_vi},
                "tokens": line.tokens if line.tokens else [],
                "flag": 1 if line.flag is None else line.flag,
            }
            for line in passage.lines
        ]
        return {
            "passage_id": passage.passage_id,
            "hsk_level": passage.hsk_level,
            "book_code": passage.book_code,
            "lines": lines,
        }
    finally:
        SessionLocal.remove()


def get_passage_book_code(passage_id: str) -> str | None:
    """Return a passage's book_code (e.g. 'AML'), or None for regular HSK passages."""
    session = SessionLocal()
    try:
        return PassageRepository(session).get_book_code(passage_id)
    finally:
        SessionLocal.remove()


def get_lesson_passage_ids_like(pattern: str) -> list[str]:
    """Passage ids matching a LIKE pattern (e.g. 'H1_2_%'), ordered."""
    session = SessionLocal()
    try:
        return PassageRepository(session).get_ids_like(pattern)
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


# ---------------------------------------------------------------------------
# LessonLine — single-row CRUD, nested under the passage aggregate.
#
# LessonPassage is the aggregate root (entity/passage/repository.py); a line
# is never managed through a standalone lesson_line service. These functions
# let a caller add/update/delete one line without resending the whole
# "lines" array via create_passage/update_passage.
# ---------------------------------------------------------------------------

def list_passage_lines(passage_id: str) -> list[dict]:
    """
    Return every line of a passage, ordered by line_id.

    Raises:
        PassageServiceError(404): if the passage does not exist.
    """
    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        _require_passage(repo, passage_id)
        passage = repo.get_by_id(passage_id)
        return [line.to_dict() for line in passage.lines]
    finally:
        SessionLocal.remove()


def get_passage_line(passage_id: str, line_id: int) -> dict:
    """
    Return a single line by (passage_id, line_id).

    Raises:
        PassageServiceError(404): if the passage or line does not exist.
    """
    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        _require_passage(repo, passage_id)
        line = repo.get_line(passage_id, line_id)
        if not line:
            raise PassageServiceError(f"Line {line_id} not found in passage '{passage_id}'.", 404)
        return line.to_dict()
    finally:
        SessionLocal.remove()


def add_passage_line(passage_id: str, data: dict) -> dict:
    """
    Add a single line to an existing passage.

    Required fields: "line_id"
    Optional fields: speaker, content, pinyin, audio_key,
                      translation_en, translation_vi, tokens (list)

    Raises:
        PassageServiceError(400): validation failure.
        PassageServiceError(404): if the passage does not exist.
        PassageServiceError(409): if the (passage_id, line_id) pair already exists.
    """
    clean = _validate_line(data, 0)
    line_id = _validate_line_id(data.get("line_id"))
    clean["line_id"] = line_id

    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        _require_passage(repo, passage_id)

        if repo.get_line(passage_id, line_id):
            raise PassageServiceError(
                f"Line {line_id} already exists in passage '{passage_id}'. Use PUT to update it.", 409
            )

        line = repo.add_line(passage_id, clean)
        session.commit()
        return line.to_dict()
    except PassageServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise PassageServiceError(
            f"Line {line_id} already exists in passage '{passage_id}'.", 409
        )
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_passage_line(passage_id: str, line_id: int, data: dict) -> dict:
    """
    Update fields on a single existing line.

    Raises:
        PassageServiceError(400): if no fields are provided, or validation fails.
        PassageServiceError(404): if the line does not exist.
        PassageServiceError(409): if changing `line_id` collides with another line.
    """
    if not data:
        raise PassageServiceError("No fields provided to update.")
    clean = _validate_line(data, 0)
    if "line_id" in clean:
        clean["line_id"] = _validate_line_id(clean["line_id"])

    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        line = repo.update_line(passage_id, line_id, clean)
        if not line:
            raise PassageServiceError(f"Line {line_id} not found in passage '{passage_id}'.", 404)
        session.commit()
        return line.to_dict()
    except PassageServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise PassageServiceError(
            f"Line {data.get('line_id')} already exists in passage '{passage_id}'.", 409
        )
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def delete_passage_line(passage_id: str, line_id: int) -> dict:
    """
    Delete a single line from a passage.

    Raises:
        PassageServiceError(404): if the line does not exist.
    """
    session = SessionLocal()
    try:
        repo = PassageRepository(session)
        deleted = repo.delete_line(passage_id, line_id)
        if not deleted:
            raise PassageServiceError(f"Line {line_id} not found in passage '{passage_id}'.", 404)
        session.commit()
        return {"message": f"Line {line_id} deleted from passage '{passage_id}'."}
    except PassageServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
