"""
routes/grammar_context_crud_routes.py
----------------------------------------
CRUD API Blueprint for the `grammar_context` table.

All endpoints are publicly accessible (no @login_required), matching the
other /api/admin CRUD blueprints.

Prefix: /api/admin/grammar_context

Endpoints:
    POST   /api/admin/grammar_context/query              → list (paginated, validated body + filter)
    GET    /api/admin/grammar_context/<int:context_id>    → get single
    POST   /api/admin/grammar_context                     → create
    PUT    /api/admin/grammar_context/<int:context_id>    → update
    DELETE /api/admin/grammar_context/<int:context_id>    → delete

List query params: page, page_size, grammar_id
"""

from flask import Blueprint, request, jsonify

from entity.grammar_context.service import (
    GrammarContextServiceError,
    list_grammar_contexts,
    get_grammar_context,
    create_grammar_context,
    update_grammar_context,
    delete_grammar_context,
)
from entity.grammar_context.schemas import GrammarContextQuery
from routes.validation import parse_body, RequestValidationError

grammar_context_crud_bp = Blueprint(
    "grammar_context_crud", __name__, url_prefix="/api/admin/grammar_context"
)


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: GrammarContextServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# POST /api/admin/grammar_context/query
# Body (JSON): { "page": 1, "page_size": 20, "grammar_id": "H1-2-1" }  (all optional)
# Replaces the former GET list — the filter now travels in a validated body.
# ---------------------------------------------------------------------------
@grammar_context_crud_bp.route("/query", methods=["POST"])
def query_grammar_contexts_endpoint():
    """List grammar contexts from a validated JSON body (optional grammar_id filter)."""
    try:
        params = parse_body(GrammarContextQuery)
    except RequestValidationError as exc:
        return exc.response()

    result = list_grammar_contexts(
        page=params.page, page_size=params.page_size, grammar_id=params.grammar_id
    )
    return _ok(result, 200)


# ---------------------------------------------------------------------------
# GET /api/admin/grammar_context/<context_id>
# ---------------------------------------------------------------------------
@grammar_context_crud_bp.route("/<int:context_id>", methods=["GET"])
def get_grammar_context_endpoint(context_id: int):
    """Get a single grammar context by its numeric ID."""
    try:
        result = get_grammar_context(context_id)
        return _ok(result, 200)
    except GrammarContextServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/grammar_context
# Body (JSON):
#   { "grammar_id": "H1-2-1", "content_json": {...} }
# ---------------------------------------------------------------------------
@grammar_context_crud_bp.route("", methods=["POST"])
def create_grammar_context_endpoint():
    """Create a new grammar context. Required: grammar_id."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = create_grammar_context(data)
        return _ok(result, 201)
    except GrammarContextServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/grammar_context/<context_id>
# Body (JSON): any subset of grammar context fields to update
# ---------------------------------------------------------------------------
@grammar_context_crud_bp.route("/<int:context_id>", methods=["PUT"])
def update_grammar_context_endpoint(context_id: int):
    """Update an existing grammar context. Send only fields you want to change."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_grammar_context(context_id, data)
        return _ok(result, 200)
    except GrammarContextServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/grammar_context/<context_id>
# ---------------------------------------------------------------------------
@grammar_context_crud_bp.route("/<int:context_id>", methods=["DELETE"])
def delete_grammar_context_endpoint(context_id: int):
    """Delete a grammar context by its numeric ID."""
    try:
        result = delete_grammar_context(context_id)
        return _ok(result, 200)
    except GrammarContextServiceError as exc:
        return _handle_service_error(exc)
