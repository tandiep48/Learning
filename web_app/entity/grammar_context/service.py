"""
entity/grammar_context/service.py
------------------------------------
Business logic and validation for the GrammarContext CRUD API.

Responsibilities:
  - Validate required fields.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

from entity.database import SessionLocal
from entity.grammar_context.entity import GrammarContext
from entity.grammar_context.repository import GrammarContextRepository
from entity.validation import require_str


class GrammarContextServiceError(Exception):
    """Raised for business-rule violations (400/404-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, 100))


def _clamp_page(page: int) -> int:
    return max(1, page)


def _validate_content_json(value):
    """`content_json` (JSONB) must be a JSON object or array, or null."""
    if value is None:
        return None
    if not isinstance(value, (dict, list)):
        raise GrammarContextServiceError("Field 'content_json' must be a JSON object or array, or null.")
    return value


def _to_dict(context: GrammarContext) -> dict:
    return {
        "id": context.id,
        "grammar_id": context.grammar_id,
        "content_json": context.content_json,
    }


def list_grammar_contexts(
    page: int = 1,
    page_size: int = 20,
    grammar_id: str | None = None,
) -> dict:
    """
    Return a paginated list of grammar contexts.

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
        repo = GrammarContextRepository(session)
        items, total = repo.get_all(page=page, page_size=page_size, grammar_id=grammar_id)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": [_to_dict(c) for c in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    finally:
        SessionLocal.remove()


def get_grammar_context(context_id: int) -> dict:
    """
    Return a single grammar context by ID.

    Raises:
        GrammarContextServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        context = GrammarContextRepository(session).get_by_id(context_id)
        if not context:
            raise GrammarContextServiceError(f"Grammar context with id={context_id} not found.", 404)
        return _to_dict(context)
    finally:
        SessionLocal.remove()


def create_grammar_context(data: dict) -> dict:
    """
    Create a new grammar context.

    Required fields: "grammar_id"

    Raises:
        GrammarContextServiceError(400): if "grammar_id" is missing.
    """
    grammar_id = require_str(GrammarContextServiceError, "grammar_id", data.get("grammar_id"), 50)
    payload = {"grammar_id": grammar_id}
    if "content_json" in data:
        payload["content_json"] = _validate_content_json(data["content_json"])

    session = SessionLocal()
    try:
        repo = GrammarContextRepository(session)
        context = repo.create(payload)
        session.commit()
        return _to_dict(context)
    except GrammarContextServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_grammar_context(context_id: int, data: dict) -> dict:
    """
    Update an existing grammar context.

    Raises:
        GrammarContextServiceError(404): if not found.
        GrammarContextServiceError(400): if no fields are provided, or `grammar_id` is blank.
    """
    if not data:
        raise GrammarContextServiceError("No fields provided to update.")

    payload: dict = {}
    if "grammar_id" in data:
        payload["grammar_id"] = require_str(GrammarContextServiceError, "grammar_id", data["grammar_id"], 50)
    if "content_json" in data:
        payload["content_json"] = _validate_content_json(data["content_json"])

    if not payload:
        raise GrammarContextServiceError("No updatable fields provided.")

    session = SessionLocal()
    try:
        repo = GrammarContextRepository(session)
        context = repo.update(context_id, payload)
        if not context:
            raise GrammarContextServiceError(f"Grammar context with id={context_id} not found.", 404)
        session.commit()
        return _to_dict(context)
    except GrammarContextServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def delete_grammar_context(context_id: int) -> dict:
    """
    Delete a grammar context by ID.

    Raises:
        GrammarContextServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = GrammarContextRepository(session)
        deleted = repo.delete(context_id)
        if not deleted:
            raise GrammarContextServiceError(f"Grammar context with id={context_id} not found.", 404)
        session.commit()
        return {"message": f"Grammar context id={context_id} deleted successfully."}
    except GrammarContextServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
