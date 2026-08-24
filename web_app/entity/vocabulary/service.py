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
from entity.vocabulary.repository import VocabRepository


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
    search: str | None = None,
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
        items, total = repo.get_all(
            page=page,
            page_size=page_size,
            hsk_level=hsk_level or None,
            search=(search or "").strip() or None,
        )
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


# ---------------------------------------------------------------------------
# Content lookups (course-wide vocab access used by the trainer/dashboard)
# ---------------------------------------------------------------------------

def get_course_vocab():
    """Every vocabulary row as a pandas DataFrame, ordered by hsk_level then id."""
    import pandas as pd

    session = SessionLocal()
    try:
        items = VocabRepository(session).get_all_ordered()
        return pd.DataFrame(
            [(v.cn, v.pinyin, v.meaning_vn, v.meaning_en, v.audio_key, v.hsk_level) for v in items],
            columns=["word", "pinyin", "meaning_vn", "meaning_en", "audio_key", "level"],
        )
    finally:
        SessionLocal.remove()


def get_vocab_lessons(hsk_level: str, lesson_size: int = 10) -> list[dict]:
    """
    Returns a list of lesson groups for a given HSK level.
    Each lesson contains lesson_size words.
    Returns: [{lesson: 1, start_idx: 0, end_idx: 9, word_count: 10, preview: ['你','好',...]}, ...]
    """
    session = SessionLocal()
    try:
        words = VocabRepository(session).get_words_by_hsk_level(hsk_level)
        lessons = []
        for i in range(0, len(words), lesson_size):
            chunk = words[i:i + lesson_size]
            lessons.append({
                "lesson": (i // lesson_size) + 1,
                "start_idx": i,
                "end_idx": i + len(chunk) - 1,
                "word_count": len(chunk),
                "preview": chunk[:4],  # first 4 words as preview
            })
        return lessons
    except Exception as e:
        print(f"⚠️ Database query failed (get_vocab_lessons): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_all_vn_meanings() -> list[str]:
    """Every distinct, non-empty Vietnamese meaning."""
    session = SessionLocal()
    try:
        return VocabRepository(session).get_distinct_vn_meanings()
    finally:
        SessionLocal.remove()


def get_vocabulary_by_words(words: list[str]) -> list[dict]:
    """Vocabulary rows for a set of Chinese words (used by the dashboard word cards)."""
    words = [w for w in (words or []) if w]
    if not words:
        return []
    session = SessionLocal()
    try:
        items = VocabRepository(session).get_by_words(words)
        return [
            {
                "word": v.cn, "pinyin": v.pinyin, "meaning_vn": v.meaning_vn,
                "meaning_en": v.meaning_en, "audio_key": v.audio_key, "hsk_level": v.hsk_level,
            }
            for v in items
        ]
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
