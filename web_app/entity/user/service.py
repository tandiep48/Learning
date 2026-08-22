"""
service/user_service.py
-------------------------
Business logic and validation for the User CRUD API.

Responsibilities:
  - Validate required/optional fields (username, email, password, level).
  - Hash passwords (werkzeug) before they reach the repository.
  - Guard against duplicate username / email.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — password hashes never leak out.
"""

from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from entity.database import SessionLocal
from entity.user.repository import UserRepository
from db.records import get_learned_words


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class UserServiceError(Exception):
    """Raised for business-rule violations (400/404/409-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, 100))


def _clamp_page(page: int) -> int:
    return max(1, page)


def _validate_username(username: str) -> str:
    name = (username or "").strip()
    if not name:
        raise UserServiceError("Field 'username' is required.")
    if len(name) > 50:
        raise UserServiceError("Field 'username' must be 50 characters or fewer.")
    return name


def _validate_email(email: str) -> str:
    value = (email or "").strip()
    if not value:
        raise UserServiceError("Field 'email' is required.")
    if len(value) > 50:
        raise UserServiceError("Field 'email' must be 50 characters or fewer.")
    if not _EMAIL_PATTERN.match(value):
        raise UserServiceError("Field 'email' is not a valid email address.")
    return value


def _validate_level(level) -> int:
    try:
        return int(level)
    except (TypeError, ValueError):
        raise UserServiceError("Field 'level' must be an integer.")


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def list_users(
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> dict:
    """
    Return a paginated list of users (password hashes excluded).

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
        repo = UserRepository(session)
        items, total = repo.get_all(
            page=page,
            page_size=page_size,
            search=(search or "").strip() or None,
        )
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": [u.to_dict() for u in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    finally:
        SessionLocal.remove()


def get_user(user_id: int) -> dict:
    """
    Return a single user by ID.

    Raises:
        UserServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = UserRepository(session)
        user = repo.get_by_id(user_id)
        if not user:
            raise UserServiceError(f"User with id={user_id} not found.", 404)
        return user.to_dict()
    finally:
        SessionLocal.remove()


def create_user(data: dict) -> dict:
    """
    Create a new user.

    Required fields: "username", "email", "password"
    Optional fields: "level" (defaults to 1)

    Raises:
        UserServiceError(400): validation failure.
        UserServiceError(409): duplicate username or email.
    """
    username = _validate_username(data.get("username", ""))
    email = _validate_email(data.get("email", ""))

    password = data.get("password") or ""
    if not password:
        raise UserServiceError("Field 'password' is required.")

    level = _validate_level(data["level"]) if "level" in data else 1

    session = SessionLocal()
    try:
        repo = UserRepository(session)
        if repo.get_by_username(username):
            raise UserServiceError(f"Username '{username}' is already taken.", 409)
        if repo.get_by_email(email):
            raise UserServiceError(f"Email '{email}' is already registered.", 409)

        user = repo.create({
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "level": level,
        })
        session.commit()
        return user.to_dict()
    except UserServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise UserServiceError("Username or email already exists.", 409)
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_user(user_id: int, data: dict) -> dict:
    """
    Update an existing user. Only provided fields are changed.

    Allowed fields: "username", "email", "password", "level"
    A provided "password" is re-hashed; it is never stored in plain text.

    Raises:
        UserServiceError(404): if not found.
        UserServiceError(400): validation failure.
        UserServiceError(409): username/email conflicts with another user.
    """
    if not data:
        raise UserServiceError("No fields provided to update.")

    payload: dict = {}
    if "username" in data:
        payload["username"] = _validate_username(data["username"])
    if "email" in data:
        payload["email"] = _validate_email(data["email"])
    if "level" in data:
        payload["level"] = _validate_level(data["level"])
    if "password" in data:
        password = data.get("password") or ""
        if not password:
            raise UserServiceError("Field 'password' cannot be empty.")
        payload["password"] = generate_password_hash(password)

    if not payload:
        raise UserServiceError("No updatable fields provided.")

    session = SessionLocal()
    try:
        repo = UserRepository(session)
        target = repo.get_by_id(user_id)
        if not target:
            raise UserServiceError(f"User with id={user_id} not found.", 404)

        # Uniqueness checks against *other* users
        if "username" in payload:
            existing = repo.get_by_username(payload["username"])
            if existing and existing.id != user_id:
                raise UserServiceError(
                    f"Username '{payload['username']}' is already taken.", 409
                )
        if "email" in payload:
            existing = repo.get_by_email(payload["email"])
            if existing and existing.id != user_id:
                raise UserServiceError(
                    f"Email '{payload['email']}' is already registered.", 409
                )

        user = repo.update(user_id, payload)
        session.commit()
        return user.to_dict()
    except UserServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise UserServiceError("Username or email already exists.", 409)
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


# ---------------------------------------------------------------------------
# Auth / Flask-Login support
# ---------------------------------------------------------------------------

def get_user_auth_by_username(username: str) -> dict | None:
    """Return a user's full auth/profile fields (including password hash), or None."""
    session = SessionLocal()
    try:
        user = UserRepository(session).get_by_username(username)
        return user.to_auth_dict() if user else None
    finally:
        SessionLocal.remove()


def get_user_auth_by_id(user_id: int) -> dict | None:
    """Return a user's full auth/profile fields (including password hash), or None."""
    session = SessionLocal()
    try:
        user = UserRepository(session).get_by_id(user_id)
        return user.to_auth_dict() if user else None
    finally:
        SessionLocal.remove()


def username_or_email_exists(username: str, email: str) -> bool:
    """Return True if a user with this username or email already exists."""
    session = SessionLocal()
    try:
        return UserRepository(session).exists_by_username_or_email(username, email)
    finally:
        SessionLocal.remove()


# ---------------------------------------------------------------------------
# HSK level progression
# ---------------------------------------------------------------------------

def _level_passes(level: int, lesson_pct: float, word_pct: float) -> bool:
    """Per-band pass rule for HSK level progression (see recompute_user_level)."""
    if level in (1, 2):
        return lesson_pct >= 85 or (word_pct >= 85 and lesson_pct >= 50)
    if level in (3, 4):
        return lesson_pct >= 80 or (word_pct >= 80 and lesson_pct >= 50)
    if level == 5:
        return lesson_pct >= 75 or (word_pct >= 75 and lesson_pct >= 40)
    if level == 6:
        return lesson_pct >= 70 or (word_pct >= 70 and lesson_pct >= 40)
    return False


def recompute_user_level(user_id: int) -> int | None:
    """
    Derive and (if higher) persist the user's HSK level from lesson-trainer progress.
    For each level compute lesson% (completed parts / total parts across ALL lessons at
    that level) and word% (mastered / total lesson words at that level), then apply the
    per-band pass rule in _level_passes. The user jumps to (highest passed level + 1),
    capped at HSK 6, and the level never decreases. Returns the resulting level, or
    None on failure.
    """
    session = SessionLocal()
    try:
        repo = UserRepository(session)
        learned = get_learned_words(user_id)
        progress = repo.get_level_progress_by_level(user_id, learned)

        user = repo.get_by_id(user_id)
        current = int(user.level) if user and user.level else 1

        highest_passed = 0
        for level, stats in progress.items():
            lesson_pct = (stats["lesson_done"] / stats["lesson_total"] * 100) if stats["lesson_total"] else 0
            word_pct = (stats["word_done"] / stats["word_total"] * 100) if stats["word_total"] else 0
            if _level_passes(level, lesson_pct, word_pct):
                highest_passed = level

        target = min(6, highest_passed + 1) if highest_passed >= 1 else 1
        target = min(6, max(current, target))  # never decrease

        if target > current:
            repo.set_level(user_id, target)
            session.commit()
        return target
    except Exception as e:
        print(f"recompute_user_level failed: {e}")
        session.rollback()
        return None
    finally:
        SessionLocal.remove()


# ---------------------------------------------------------------------------
# Profile settings (avatar, Hanzi font/script, UI language, password)
# ---------------------------------------------------------------------------

DEFAULT_HANZI_FONT = "Noto Sans"
DEFAULT_HANZI_SCRIPT = "simplified"
DEFAULT_UI_LANGUAGE = "en"


def _update_setting(user_id: int, **values) -> bool:
    session = SessionLocal()
    try:
        updated = UserRepository(session).update(user_id, values)
        if updated is None:
            return False
        session.commit()
        return True
    except Exception as e:
        print(f"Update user setting failed ({list(values)}): {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()


def update_user_avatar_path(user_id: int, avatar_path: str) -> bool:
    return _update_setting(user_id, avatar_path=avatar_path)


def get_user_hanzi_font(user_id: int) -> str:
    session = SessionLocal()
    try:
        user = UserRepository(session).get_by_id(user_id)
        return (user.hanzi_font if user else None) or DEFAULT_HANZI_FONT
    finally:
        SessionLocal.remove()


def update_user_hanzi_font(user_id: int, hanzi_font: str) -> bool:
    return _update_setting(user_id, hanzi_font=hanzi_font)


def get_user_hanzi_script(user_id: int) -> str:
    session = SessionLocal()
    try:
        user = UserRepository(session).get_by_id(user_id)
        return (user.hanzi_script if user else None) or DEFAULT_HANZI_SCRIPT
    finally:
        SessionLocal.remove()


def update_user_hanzi_script(user_id: int, hanzi_script: str) -> bool:
    return _update_setting(user_id, hanzi_script=hanzi_script)


def get_user_ui_language(user_id: int) -> str:
    session = SessionLocal()
    try:
        user = UserRepository(session).get_by_id(user_id)
        return (user.ui_language if user else None) or DEFAULT_UI_LANGUAGE
    finally:
        SessionLocal.remove()


def update_user_ui_language(user_id: int, ui_language: str) -> bool:
    return _update_setting(user_id, ui_language=ui_language)


def update_user_password(user_id: int, password_hash: str) -> bool:
    return _update_setting(user_id, password=password_hash)


def get_profile_summary(user_id: int) -> dict:
    """
    Return per-mode/skill time-spent totals for the vocab, lesson, and
    practice/exam activity records, plus grand totals per bucket.
    """
    summary = {
        "time_totals_ms": {"vocab": 0, "lesson": 0, "practice": 0, "exam": 0},
        "vocab_mode_time_ms": [],
        "lesson_mode_time_ms": [],
        "practice_skill_time_ms": [],
    }

    session = SessionLocal()
    try:
        raw = UserRepository(session).get_profile_summary(user_id)

        summary["vocab_mode_time_ms"] = [
            {"mode": mode, "time_ms": time_ms} for mode, time_ms in raw["vocab_mode_time_ms"]
        ]
        summary["time_totals_ms"]["vocab"] = sum(
            item["time_ms"] for item in summary["vocab_mode_time_ms"]
        )

        lesson_mode_names = {1: "meaning", 2: "typing", 3: "reorder", 4: "listening"}
        summary["lesson_mode_time_ms"] = [
            {"mode": lesson_mode_names.get(mode, str(mode)), "time_ms": time_ms}
            for mode, time_ms in raw["lesson_mode_time_ms"]
        ]
        summary["time_totals_ms"]["lesson"] = sum(
            item["time_ms"] for item in summary["lesson_mode_time_ms"]
        )

        summary["practice_skill_time_ms"] = [
            {"category": cat, "skill": skill, "time_ms": time_ms}
            for cat, skill, time_ms in raw["practice_skill_time_ms"]
        ]
        for item in summary["practice_skill_time_ms"]:
            cat = item["category"] if item["category"] in ("practice", "exam") else "practice"
            summary["time_totals_ms"][cat] += item["time_ms"]

        return summary
    except Exception as e:
        print(f"get_profile_summary failed: {e}")
        return summary
    finally:
        SessionLocal.remove()


def delete_user(user_id: int) -> dict:
    """
    Delete a user by ID.

    Raises:
        UserServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = UserRepository(session)
        deleted = repo.delete(user_id)
        if not deleted:
            raise UserServiceError(f"User with id={user_id} not found.", 404)
        session.commit()
        return {"message": f"User id={user_id} deleted successfully."}
    except UserServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
