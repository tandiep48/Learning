"""
service/question_service.py
-----------------------------
Business logic and validation for the Question Bank CRUD API.

Responsibilities:
  - Validate required/optional fields and enum values.
  - Guard against duplicate (category, level, lesson, no) keys.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from entity.database import SessionLocal
from repository.question_repository import QuestionRepository


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

CATEGORIES = {"practice", "exam"}
SKILLS = {"listening", "reading"}


class QuestionServiceError(Exception):
    """Raised for business-rule violations (400/404/409-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, 100))


def _clamp_page(page: int) -> int:
    return max(1, page)


def _as_int(field: str, value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise QuestionServiceError(f"Field '{field}' must be an integer.")


def _validate_category(value) -> str:
    category = (value or "").strip() if isinstance(value, str) else value
    if category not in CATEGORIES:
        raise QuestionServiceError(
            f"Field 'category' must be one of: {', '.join(sorted(CATEGORIES))}."
        )
    return category


def _validate_skill(value) -> str | None:
    if value in (None, ""):
        return None
    skill = value.strip() if isinstance(value, str) else value
    if skill not in SKILLS:
        raise QuestionServiceError(
            f"Field 'skill' must be one of: {', '.join(sorted(SKILLS))} (or empty)."
        )
    return skill


def _validate_progress(value) -> str:
    progress = (value or "").strip()
    if not progress:
        raise QuestionServiceError("Field 'progress' is required.")
    if len(progress) > 30:
        raise QuestionServiceError("Field 'progress' must be 30 characters or fewer.")
    return progress


def _validate_options(value):
    """Options must be a JSON object (dict) or null."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise QuestionServiceError("Field 'options' must be a JSON object or null.")
    return value


def _validate_len(field: str, value, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) > max_len:
        raise QuestionServiceError(f"Field '{field}' must be {max_len} characters or fewer.")
    return text


def _build_payload(data: dict, *, partial: bool) -> dict:
    """
    Validate incoming fields and return a clean payload.

    When `partial` is False (create), the required fields must be present.
    When `partial` is True (update), only the provided fields are validated.
    """
    payload: dict = {}

    def present(field):
        return field in data

    # ── required-on-create fields ──────────────────────────────────────────
    if present("category") or not partial:
        payload["category"] = _validate_category(data.get("category"))
    if present("level") or not partial:
        payload["level"] = _as_int("level", data.get("level"))
    if present("lesson") or not partial:
        payload["lesson"] = _as_int("lesson", data.get("lesson"))
    if present("no") or not partial:
        payload["no"] = _as_int("no", data.get("no"))
    if present("type") or not partial:
        payload["type"] = _as_int("type", data.get("type"))
    if present("progress") or not partial:
        payload["progress"] = _validate_progress(data.get("progress"))

    # ── optional fields ────────────────────────────────────────────────────
    if present("skill"):
        payload["skill"] = _validate_skill(data.get("skill"))
    if present("options"):
        payload["options"] = _validate_options(data.get("options"))
    if present("answer"):
        payload["answer"] = _validate_len("answer", data.get("answer"), 50)
    if present("image"):
        payload["image"] = _validate_len("image", data.get("image"), 255)
    if present("unit_id"):
        payload["unit_id"] = _validate_len("unit_id", data.get("unit_id") or "", 20)
    for field in ("content", "question", "audio_key"):
        if present(field):
            payload[field] = data.get(field)

    if not partial:
        payload.setdefault("unit_id", "")

    return payload


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def list_questions(
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    level=None,
    lesson=None,
    skill: str | None = None,
    search: str | None = None,
) -> dict:
    """Return a paginated list of questions with optional filters."""
    page = _clamp_page(page)
    page_size = _clamp_page_size(page_size)

    filters = {
        "category": _validate_category(category) if category else None,
        "level": _as_int("level", level) if level not in (None, "") else None,
        "lesson": _as_int("lesson", lesson) if lesson not in (None, "") else None,
        "skill": _validate_skill(skill) if skill else None,
        "search": (search or "").strip() or None,
    }

    session = SessionLocal()
    try:
        repo = QuestionRepository(session)
        items, total = repo.get_all(page=page, page_size=page_size, **filters)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": [q.to_dict() for q in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    finally:
        SessionLocal.remove()


def get_question(question_id: int) -> dict:
    """
    Return a single question by ID.

    Raises:
        QuestionServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = QuestionRepository(session)
        question = repo.get_by_id(question_id)
        if not question:
            raise QuestionServiceError(f"Question with id={question_id} not found.", 404)
        return question.to_dict()
    finally:
        SessionLocal.remove()


def create_question(data: dict) -> dict:
    """
    Create a new question.

    Required fields: category, level, lesson, no, type, progress
    Optional fields: skill, content, question, answer, audio_key, image,
                     options (JSON object), unit_id

    Raises:
        QuestionServiceError(400): validation failure.
        QuestionServiceError(409): duplicate (category, level, lesson, no).
    """
    payload = _build_payload(data, partial=False)

    session = SessionLocal()
    try:
        repo = QuestionRepository(session)
        if repo.get_by_unique(
            payload["category"], payload["level"], payload["lesson"], payload["no"]
        ):
            raise QuestionServiceError(
                f"A {payload['category']} question already exists for "
                f"level {payload['level']}, lesson {payload['lesson']}, no {payload['no']}.",
                409,
            )

        question = repo.create(payload)
        session.commit()
        return question.to_dict()
    except QuestionServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise QuestionServiceError(
            "A question with the same category, level, lesson and no already exists.", 409
        )
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_question(question_id: int, data: dict) -> dict:
    """
    Update an existing question. Only provided fields are changed.

    Raises:
        QuestionServiceError(404): if not found.
        QuestionServiceError(400): validation failure.
        QuestionServiceError(409): the change collides with another question's
                                   (category, level, lesson, no) key.
    """
    if not data:
        raise QuestionServiceError("No fields provided to update.")

    payload = _build_payload(data, partial=True)
    if not payload:
        raise QuestionServiceError("No updatable fields provided.")

    session = SessionLocal()
    try:
        repo = QuestionRepository(session)
        target = repo.get_by_id(question_id)
        if not target:
            raise QuestionServiceError(f"Question with id={question_id} not found.", 404)

        # If any part of the unique key changes, ensure no other row collides.
        key_fields = ("category", "level", "lesson", "no")
        if any(f in payload for f in key_fields):
            category = payload.get("category", target.category)
            level = payload.get("level", target.level)
            lesson = payload.get("lesson", target.lesson)
            no = payload.get("no", target.no)
            existing = repo.get_by_unique(category, level, lesson, no)
            if existing and existing.id != question_id:
                raise QuestionServiceError(
                    f"A {category} question already exists for "
                    f"level {level}, lesson {lesson}, no {no}.",
                    409,
                )

        question = repo.update(question_id, payload)
        session.commit()
        return question.to_dict()
    except QuestionServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise QuestionServiceError(
            "A question with the same category, level, lesson and no already exists.", 409
        )
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def delete_question(question_id: int) -> dict:
    """
    Delete a question by ID.

    Raises:
        QuestionServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = QuestionRepository(session)
        deleted = repo.delete(question_id)
        if not deleted:
            raise QuestionServiceError(f"Question with id={question_id} not found.", 404)
        session.commit()
        return {"message": f"Question id={question_id} deleted successfully."}
    except QuestionServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
