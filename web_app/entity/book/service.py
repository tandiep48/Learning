"""
entity/book/service.py
------------------------
Business logic and validation for the Book CRUD API.

Responsibilities:
  - Validate required fields and book_code format.
  - Guard against duplicate book_code on create.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError

from entity.database import SessionLocal
from entity.book.entity import Book
from entity.book.repository import BookRepository


class BookServiceError(Exception):
    """Raised for business-rule violations (400/404-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


_BOOK_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")


def _validate_book_code(book_code: str) -> str:
    code = (book_code or "").strip()
    if not code:
        raise BookServiceError("Field 'book_code' is required.")
    if not _BOOK_CODE_PATTERN.match(code):
        raise BookServiceError(
            "Field 'book_code' may only contain letters, digits, underscores, and hyphens."
        )
    return code


def _to_dict(book: Book) -> dict:
    return {
        "book_code": book.book_code,
        "name_en": book.name_en,
        "name_vn": book.name_vn,
    }


def list_books() -> list[dict]:
    """Return every book."""
    session = SessionLocal()
    try:
        books = BookRepository(session).get_all()
        return [_to_dict(b) for b in books]
    finally:
        SessionLocal.remove()


def get_book(book_code: str) -> dict:
    """
    Return a single book.

    Raises:
        BookServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        book = BookRepository(session).get_by_code(book_code)
        if not book:
            raise BookServiceError(f"Book '{book_code}' not found.", 404)
        return _to_dict(book)
    finally:
        SessionLocal.remove()


def create_book(data: dict) -> dict:
    """
    Create a new book.

    Required fields: "book_code"
    Optional fields: "name_en", "name_vn"

    Raises:
        BookServiceError(400): validation failure or duplicate.
    """
    code = _validate_book_code(data.get("book_code", ""))
    data = {**data, "book_code": code}

    session = SessionLocal()
    try:
        repo = BookRepository(session)
        if repo.get_by_code(code):
            raise BookServiceError(f"Book '{code}' already exists. Use PUT to update it.")

        book = repo.create(data)
        session.commit()
        return _to_dict(book)
    except BookServiceError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise BookServiceError(f"Book '{code}' already exists.")
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_book(book_code: str, data: dict) -> dict:
    """
    Update an existing book.

    Allowed fields: "name_en", "name_vn"

    Raises:
        BookServiceError(404): if not found.
        BookServiceError(400): if no fields are provided.
    """
    if not data:
        raise BookServiceError("No fields provided to update.")

    session = SessionLocal()
    try:
        repo = BookRepository(session)
        book = repo.update(book_code, data)
        if not book:
            raise BookServiceError(f"Book '{book_code}' not found.", 404)
        session.commit()
        return _to_dict(book)
    except BookServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def delete_book(book_code: str) -> dict:
    """
    Delete a book.

    Raises:
        BookServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = BookRepository(session)
        deleted = repo.delete(book_code)
        if not deleted:
            raise BookServiceError(f"Book '{book_code}' not found.", 404)
        session.commit()
        return {"message": f"Book '{book_code}' deleted successfully."}
    except BookServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
