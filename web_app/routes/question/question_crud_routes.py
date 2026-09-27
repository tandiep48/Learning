"""
routes/question_crud_routes.py
--------------------------------
CRUD API Blueprint for the `question_bank` table (admin management).

All endpoints are publicly accessible (no @login_required), matching the
other /api/admin CRUD blueprints.

Prefix: /api/admin/question

Endpoints:
    POST   /api/admin/question/query                → list (paginated, validated body + filters)
    GET    /api/admin/question/<int:question_id>    → get single
    POST   /api/admin/question                      → create
    PUT    /api/admin/question/<int:question_id>    → update
    DELETE /api/admin/question/<int:question_id>    → delete

List body fields: page, page_size, category, level, lesson, skill, search
"""

from flask import Blueprint, request, jsonify

from entity.question.service import (
    QuestionServiceError,
    list_questions,
    get_question,
    create_question,
    update_question,
    delete_question,
)
from entity.question.schemas import QuestionQuery
from routes.validation import parse_body, RequestValidationError

question_crud_bp = Blueprint("question_crud", __name__, url_prefix="/api/admin/question")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: QuestionServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# POST /api/admin/question/query
# Body (JSON): { "page", "page_size", "category", "level", "lesson", "skill", "search" }
# All fields optional. Replaces the former GET list — filters now travel in a
# validated body.
# ---------------------------------------------------------------------------
@question_crud_bp.route("/query", methods=["POST"])
def query_questions_endpoint():
    """List questions from a validated JSON body (optional filters + search)."""
    try:
        params = parse_body(QuestionQuery)
    except RequestValidationError as exc:
        return exc.response()

    try:
        result = list_questions(
            page=params.page,
            page_size=params.page_size,
            category=params.category,
            level=params.level,
            lesson=params.lesson,
            skill=params.skill,
            search=params.search,
        )
        return _ok(result, 200)
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
        return _ok(result, 200)
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
        return _ok(result, 201)
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
        return _ok(result, 200)
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
        return _ok(result, 200)
    except QuestionServiceError as exc:
        return _handle_service_error(exc)
