"""
routes/passage_line_crud_routes.py
-------------------------------------
CRUD API Blueprint for individual `lesson_lines` rows, nested under their
parent passage.

LessonPassage is the aggregate root (see entity/passage/repository.py) —
these endpoints let an admin add/update/delete one line at a time instead
of resending the whole "lines" array via PUT /api/admin/passage/<id>.

All endpoints are publicly accessible (no @login_required).

Prefix: /api/admin/passage/<passage_id>/lines

Endpoints:
    GET    /api/admin/passage/<passage_id>/lines                  → list lines
    GET    /api/admin/passage/<passage_id>/lines/<int:line_id>    → get single line
    POST   /api/admin/passage/<passage_id>/lines                  → add a line
    PUT    /api/admin/passage/<passage_id>/lines/<int:line_id>    → update a line
    DELETE /api/admin/passage/<passage_id>/lines/<int:line_id>    → delete a line

Example POST body:
    {
        "line_id": 1,
        "speaker": "A",
        "content": "你好",
        "pinyin": "nǐ hǎo",
        "audio_key": "H1_1_1_01.mp3",
        "translation_en": "Hello",
        "translation_vi": "Xin chào",
        "tokens": []
    }
"""

from flask import Blueprint, request, jsonify

from entity.passage.service import (
    PassageServiceError,
    list_passage_lines,
    get_passage_line,
    add_passage_line,
    update_passage_line,
    delete_passage_line,
)

passage_line_crud_bp = Blueprint(
    "passage_line_crud",
    __name__,
    url_prefix="/api/admin/passage/<string:passage_id>/lines",
)


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: PassageServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>/lines
# ---------------------------------------------------------------------------
@passage_line_crud_bp.route("", methods=["GET"])
def list_passage_lines_endpoint(passage_id: str):
    """List all lines of a passage, ordered by line_id."""
    try:
        result = list_passage_lines(passage_id)
        return _ok(result, 200)
    except PassageServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>/lines/<line_id>
# ---------------------------------------------------------------------------
@passage_line_crud_bp.route("/<int:line_id>", methods=["GET"])
def get_passage_line_endpoint(passage_id: str, line_id: int):
    """Get a single line by its line_id within the passage."""
    try:
        result = get_passage_line(passage_id, line_id)
        return _ok(result, 200)
    except PassageServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/passage/<passage_id>/lines
# Required: line_id
# ---------------------------------------------------------------------------
@passage_line_crud_bp.route("", methods=["POST"])
def add_passage_line_endpoint(passage_id: str):
    """Add a single line to an existing passage."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = add_passage_line(passage_id, data)
        return _ok(result, 201)
    except PassageServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/passage/<passage_id>/lines/<line_id>
# Body (JSON): any subset of line fields to update
# ---------------------------------------------------------------------------
@passage_line_crud_bp.route("/<int:line_id>", methods=["PUT"])
def update_passage_line_endpoint(passage_id: str, line_id: int):
    """Update an existing line. Send only fields you want to change."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_passage_line(passage_id, line_id, data)
        return _ok(result, 200)
    except PassageServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/passage/<passage_id>/lines/<line_id>
# ---------------------------------------------------------------------------
@passage_line_crud_bp.route("/<int:line_id>", methods=["DELETE"])
def delete_passage_line_endpoint(passage_id: str, line_id: int):
    """Delete a single line from a passage."""
    try:
        result = delete_passage_line(passage_id, line_id)
        return _ok(result, 200)
    except PassageServiceError as exc:
        return _handle_service_error(exc)
