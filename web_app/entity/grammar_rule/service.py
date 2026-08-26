"""
entity/grammar_rule/service.py
---------------------------------
Business logic for the GrammarRule CRUD API, plus the existing lesson lookup.

Responsibilities:
  - Validate required fields.
  - Manage the SQLAlchemy session lifecycle (commit / rollback).
  - Return plain dicts — no ORM objects leak into the route layer.
"""

from __future__ import annotations

from entity.database import SessionLocal
from entity.grammar_rule.entity import GrammarRule
from entity.grammar_rule.repository import GrammarRuleRepository
from entity.validation import require_str, optional_str, optional_int, optional_one_of

_COLUMNS = ["grammar_id", "type", "vietnamese_content", "english_content", "vn_context", "en_context"]

# static/grammar/grammar.js renders types 1-5 (section header, ... example dialogue);
# any other value has no known front-end rendering.
GRAMMAR_TYPES = {1, 2, 3, 4, 5}


class GrammarRuleServiceError(Exception):
    """Raised for business-rule violations (400/404-level errors)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, 100))


def _clamp_page(page: int) -> int:
    return max(1, page)


def _validate_payload(data: dict) -> dict:
    """
    Validate the optional grammar_rule fields present in `data` (type +
    length matching the table's column sizes, and the known `type` domain).
    `grammar_id` is validated by the caller since it's required on create
    but optional on update.
    """
    payload: dict = {}
    if "type" in data:
        type_ = optional_int(GrammarRuleServiceError, "type", data["type"])
        if type_ is not None:
            optional_one_of(GrammarRuleServiceError, "type", type_, GRAMMAR_TYPES)
        payload["type"] = type_
    if "passage_number" in data:
        payload["passage_number"] = optional_int(GrammarRuleServiceError, "passage_number", data["passage_number"])
    if "vietnamese_content" in data:
        payload["vietnamese_content"] = optional_str(
            GrammarRuleServiceError, "vietnamese_content", data["vietnamese_content"]
        )
    if "english_content" in data:
        payload["english_content"] = optional_str(
            GrammarRuleServiceError, "english_content", data["english_content"]
        )
    return payload


def _to_dict(rule: GrammarRule) -> dict:
    return {
        "id": rule.id,
        "grammar_id": rule.grammar_id,
        "type": rule.type,
        "passage_number": rule.passage_number,
        "vietnamese_content": rule.vietnamese_content,
        "english_content": rule.english_content,
    }


# ---------------------------------------------------------------------------
# Content lookups (used by the lesson trainer)
# ---------------------------------------------------------------------------

def get_grammar_for_lesson(hsk_level, lesson) -> list[dict]:
    """
    All grammar rules for a whole lesson (every part), ordered by insertion
    id. The caller splits the flat list into sections at each type=1 row.
    """
    session = SessionLocal()
    try:
        pattern = f"H{hsk_level}-{lesson}-%"
        rows = GrammarRuleRepository(session).get_rules_for_lesson(pattern)
        results = []
        for row in rows:
            d = dict(zip(_COLUMNS, row))
            if d.get("vn_context") is None:
                d.pop("vn_context", None)
            if d.get("en_context") is None:
                d.pop("en_context", None)
            results.append(d)
        return results
    except Exception as e:
        print(f"[WARN] get_grammar_for_lesson failed: {e}")
        return []
    finally:
        SessionLocal.remove()


# ---------------------------------------------------------------------------
# CRUD (admin management)
# ---------------------------------------------------------------------------

def list_grammar_rules(
    page: int = 1,
    page_size: int = 20,
    grammar_id: str | None = None,
    type_: int | None = None,
) -> dict:
    """
    Return a paginated list of grammar rules.

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
        repo = GrammarRuleRepository(session)
        items, total = repo.get_all(page=page, page_size=page_size, grammar_id=grammar_id, type_=type_)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": [_to_dict(r) for r in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    finally:
        SessionLocal.remove()


def get_grammar_rule(rule_id: int) -> dict:
    """
    Return a single grammar rule by ID.

    Raises:
        GrammarRuleServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        rule = GrammarRuleRepository(session).get_by_id(rule_id)
        if not rule:
            raise GrammarRuleServiceError(f"Grammar rule with id={rule_id} not found.", 404)
        return _to_dict(rule)
    finally:
        SessionLocal.remove()


def create_grammar_rule(data: dict) -> dict:
    """
    Create a new grammar rule.

    Required fields: "grammar_id"

    Raises:
        GrammarRuleServiceError(400): if "grammar_id" is missing.
    """
    grammar_id = require_str(GrammarRuleServiceError, "grammar_id", data.get("grammar_id"), 50)
    payload = _validate_payload(data)
    payload["grammar_id"] = grammar_id

    session = SessionLocal()
    try:
        repo = GrammarRuleRepository(session)
        rule = repo.create(payload)
        session.commit()
        return _to_dict(rule)
    except GrammarRuleServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_grammar_rule(rule_id: int, data: dict) -> dict:
    """
    Update an existing grammar rule.

    Raises:
        GrammarRuleServiceError(404): if not found.
        GrammarRuleServiceError(400): if no fields are provided, or `grammar_id` is blank.
    """
    if not data:
        raise GrammarRuleServiceError("No fields provided to update.")

    payload = _validate_payload(data)
    if "grammar_id" in data:
        payload["grammar_id"] = require_str(GrammarRuleServiceError, "grammar_id", data["grammar_id"], 50)

    if not payload:
        raise GrammarRuleServiceError("No updatable fields provided.")

    session = SessionLocal()
    try:
        repo = GrammarRuleRepository(session)
        rule = repo.update(rule_id, payload)
        if not rule:
            raise GrammarRuleServiceError(f"Grammar rule with id={rule_id} not found.", 404)
        session.commit()
        return _to_dict(rule)
    except GrammarRuleServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def delete_grammar_rule(rule_id: int) -> dict:
    """
    Delete a grammar rule by ID.

    Raises:
        GrammarRuleServiceError(404): if not found.
    """
    session = SessionLocal()
    try:
        repo = GrammarRuleRepository(session)
        deleted = repo.delete(rule_id)
        if not deleted:
            raise GrammarRuleServiceError(f"Grammar rule with id={rule_id} not found.", 404)
        session.commit()
        return {"message": f"Grammar rule id={rule_id} deleted successfully."}
    except GrammarRuleServiceError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
