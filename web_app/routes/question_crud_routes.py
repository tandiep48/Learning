"""
routes/question_crud_routes.py
--------------------------------
CRUD API Blueprint for the `question_bank` table (admin management).

All endpoints are publicly accessible (no @login_required), matching the
other /api/admin CRUD blueprints.

Prefix: /api/admin/question

Endpoints:
    GET    /api/admin/question                      → list (paginated + filters)
    GET    /api/admin/question/<int:question_id>    → get single
    POST   /api/admin/question                      → create
    PUT    /api/admin/question/<int:question_id>    → update
    DELETE /api/admin/question/<int:question_id>    → delete

List query params: page, page_size, category, level, lesson, skill, search
"""

from flask import Blueprint, request, jsonify

from service.question_service import (
    QuestionServiceError,
    list_questions,
    get_question,
    create_question,
    update_question,
    delete_question,
)

question_crud_bp = Blueprint("question_crud", __name__, url_prefix="/api/admin/question")


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _handle_service_error(exc: QuestionServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/question
# ---------------------------------------------------------------------------
@question_crud_bp.route("", methods=["GET"])
def list_questions_endpoint():
    """List questions with optional filters and pagination."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        return _error("'page' and 'page_size' must be integers.", 400)

    try:
        result = list_questions(
            page=page,
            page_size=page_size,
            category=request.args.get("category") or None,
            level=request.args.get("level") or None,
            lesson=request.args.get("lesson") or None,
            skill=request.args.get("skill") or None,
            search=request.args.get("search") or None,
        )
        return jsonify(result), 200
    except QuestionServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# GET /api/admin/question/<question_id>
# ---------------------------------------------------------------------------
@question_crud_bp.route("/<int:question_id>", methods=["GET"])
def get_question_endpoint(question_id: int):
    """Get a single question by numeric ID."""
    try:
        result = get_question(question_id)
        return jsonify(result), 200
    except QuestionServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/question
# ---------------------------------------------------------------------------
@question_crud_bp.route("", methods=["POST"])
def create_question_endpoint():
    """Create a new question. Required: category, level, lesson, no, type, progress."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = create_question(data)
        return jsonify(result), 201
    except QuestionServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/question/<question_id>
# ---------------------------------------------------------------------------
@question_crud_bp.route("/<int:question_id>", methods=["PUT"])
def update_question_endpoint(question_id: int):
    """Update an existing question. Send only the fields you want to change."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_question(question_id, data)
        return jsonify(result), 200
    except QuestionServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/question/<question_id>
# ---------------------------------------------------------------------------
@question_crud_bp.route("/<int:question_id>", methods=["DELETE"])
def delete_question_endpoint(question_id: int):
    """Delete a question by numeric ID."""
    try:
        result = delete_question(question_id)
        return jsonify(result), 200
    except QuestionServiceError as exc:
        return _handle_service_error(exc)
