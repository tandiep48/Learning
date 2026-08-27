"""
routes/grammar_rule_crud_routes.py
-------------------------------------
CRUD API Blueprint for the `grammar_rule` table.

All endpoints are publicly accessible (no @login_required), matching the
other /api/admin CRUD blueprints.

Prefix: /api/admin/grammar_rule

Endpoints:
    GET    /api/admin/grammar_rule                  → list (paginated + filters)
    GET    /api/admin/grammar_rule/<int:rule_id>    → get single
    POST   /api/admin/grammar_rule                  → create
    PUT    /api/admin/grammar_rule/<int:rule_id>    → update
    DELETE /api/admin/grammar_rule/<int:rule_id>    → delete

List query params: page, page_size, grammar_id, type
"""

from flask import Blueprint, request, jsonify

from entity.grammar_rule.service import (
    GrammarRuleServiceError,
    list_grammar_rules,
    get_grammar_rule,
    create_grammar_rule,
    update_grammar_rule,
    delete_grammar_rule,
)

grammar_rule_crud_bp = Blueprint("grammar_rule_crud", __name__, url_prefix="/api/admin/grammar_rule")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: GrammarRuleServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/grammar_rule
# Query params: page, page_size, grammar_id, type
# ---------------------------------------------------------------------------
@grammar_rule_crud_bp.route("", methods=["GET"])
def list_grammar_rules_endpoint():
    """List grammar rules with optional grammar_id/type filters and pagination."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        return _error("'page' and 'page_size' must be integers.", 400)

    type_param = request.args.get("type")
    try:
        type_ = int(type_param) if type_param is not None else None
    except (TypeError, ValueError):
        return _error("'type' must be an integer.", 400)

    grammar_id = request.args.get("grammar_id") or None
    result = list_grammar_rules(page=page, page_size=page_size, grammar_id=grammar_id, type_=type_)
    return _ok(result, 200)


# ---------------------------------------------------------------------------
# GET /api/admin/grammar_rule/<rule_id>
# ---------------------------------------------------------------------------
@grammar_rule_crud_bp.route("/<int:rule_id>", methods=["GET"])
def get_grammar_rule_endpoint(rule_id: int):
    """Get a single grammar rule by its numeric ID."""
    try:
        result = get_grammar_rule(rule_id)
        return _ok(result, 200)
    except GrammarRuleServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/grammar_rule
# Body (JSON):
#   { "grammar_id": "H1-2-1", "type": 1, "passage_number": 1,
#     "vietnamese_content": "...", "english_content": "..." }
# ---------------------------------------------------------------------------
@grammar_rule_crud_bp.route("", methods=["POST"])
def create_grammar_rule_endpoint():
    """Create a new grammar rule. Required: grammar_id."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = create_grammar_rule(data)
        return _ok(result, 201)
    except GrammarRuleServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/grammar_rule/<rule_id>
# Body (JSON): any subset of grammar rule fields to update
# ---------------------------------------------------------------------------
@grammar_rule_crud_bp.route("/<int:rule_id>", methods=["PUT"])
def update_grammar_rule_endpoint(rule_id: int):
    """Update an existing grammar rule. Send only fields you want to change."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_grammar_rule(rule_id, data)
        return _ok(result, 200)
    except GrammarRuleServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/grammar_rule/<rule_id>
# ---------------------------------------------------------------------------
@grammar_rule_crud_bp.route("/<int:rule_id>", methods=["DELETE"])
def delete_grammar_rule_endpoint(rule_id: int):
    """Delete a grammar rule by its numeric ID."""
    try:
        result = delete_grammar_rule(rule_id)
        return _ok(result, 200)
    except GrammarRuleServiceError as exc:
        return _handle_service_error(exc)
