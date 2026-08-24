"""
entity/chinese_stroke_info/service.py
----------------------------------------
Business logic for looking up per-word Chinese stroke info.

Manages the SQLAlchemy session lifecycle and shapes repository rows into
the plain dicts callers expect. Read-only: rows are populated by
scripts/update_h4_and_dict.py, not through this service.
"""

from __future__ import annotations

from entity.database import SessionLocal
from entity.chinese_stroke_info.repository import ChineseStrokeInfoRepository


class ChineseStrokeInfoServiceError(Exception):
    """Raised for business-rule violations (400/404-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_stroke_info(cn: str) -> dict:
    """
    Return stroke info for a single Chinese word.

    Raises:
        ChineseStrokeInfoServiceError(400): if `cn` is missing/blank.
        ChineseStrokeInfoServiceError(404): if no row exists for `cn`.
    """
    cn = (cn or "").strip()
    if not cn:
        raise ChineseStrokeInfoServiceError("Field 'cn' (Chinese word) is required.")

    session = SessionLocal()
    try:
        row = ChineseStrokeInfoRepository(session).get_by_cn(cn)
        if not row:
            raise ChineseStrokeInfoServiceError(f"Chinese stroke info for '{cn}' not found.", 404)
        return row.to_dict()
    finally:
        SessionLocal.remove()


def get_stroke_info_batch(words: list[str]) -> list[dict]:
    """
    Return stroke info for every word in `words` that has a row.
    Unknown words are silently omitted (this is a batch lookup, not a
    per-word existence check).
    """
    cleaned = []
    seen = set()
    for word in words or []:
        word = (word or "").strip()
        if word and word not in seen:
            seen.add(word)
            cleaned.append(word)

    if not cleaned:
        return []

    session = SessionLocal()
    try:
        rows = ChineseStrokeInfoRepository(session).get_by_words(cleaned)
        return [row.to_dict() for row in rows]
    finally:
        SessionLocal.remove()
