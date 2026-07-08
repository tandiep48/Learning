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
from repository.user_repository import UserRepository


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
