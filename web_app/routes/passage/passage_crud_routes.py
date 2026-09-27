"""
routes/passage_crud_routes.py
-------------------------------
CRUD API Blueprint for `lesson_passages` + `lesson_lines`.

All endpoints are publicly accessible (no @login_required).

Prefix: /api/admin/passage

Endpoints:
    POST   /api/admin/passage/query              → list passages (paginated, validated body, no lines)
    GET    /api/admin/passage/<passage_id>        → get single passage with its lines
    POST   /api/admin/passage                    → create passage (+ optional lines)
    PUT    /api/admin/passage/<passage_id>        → update passage (+ optional line replacement)
    DELETE /api/admin/passage/<passage_id>        → delete passage and all lines

Example POST body:
    {
        "passage_id": "H1_1_1",
        "hsk_level": "HSK1",
        "lines": [
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
        ]
    }
"""

from flask import Blueprint, request, jsonify

from entity.passage.service import (
    PassageServiceError,
    list_passages,
    get_passage,
    create_passage,
    update_passage,
    delete_passage,
)
from entity.passage.schemas import PassageQuery
from routes.validation import parse_body, RequestValidationError

passage_crud_bp = Blueprint("passage_crud", __name__, url_prefix="/api/admin/passage")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: PassageServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# POST /api/admin/passage/query
# Body (JSON): { "page": 1, "page_size": 20, "hsk_level": "HSK1" }  (all optional)
# Replaces the former GET list — the filter now travels in a validated body.
# ---------------------------------------------------------------------------
@passage_crud_bp.route("/query", methods=["POST"])
def query_passages_endpoint():
    """List lesson passages from a validated JSON body. Lines are NOT included."""
    try:
        params = parse_body(PassageQuery)
    except RequestValidationError as exc:
        return exc.response()

    result = list_passages(page=params.page, page_size=params.page_size, hsk_level=params.hsk_level)
    return _ok(result, 200)


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>
# ---------------------------------------------------------------------------
@passage_crud_bp.route("/<string:passage_id>", methods=["GET"])
def get_passage_endpoint(passage_id: str):
    """Get a single passage with all its lines."""
    try:
        result = get_passage(passage_id)
        return _ok(result, 200)
    except PassageServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/passage
# ---------------------------------------------------------------------------
@passage_crud_bp.route("", methods=["POST"])
def create_passage_endpoint():
    """
    Create a new passage.

    Required: passage_id
    Optional: hsk_level, lines (array of line objects)
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = create_passage(data)
        return _ok(result, 201)
    except PassageServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/passage/<passage_id>
# ---------------------------------------------------------------------------
@passage_crud_bp.route("/<string:passage_id>", methods=["PUT"])
def update_passage_endpoint(passage_id: str):
    """
    Update an existing passage.

    Allowed fields: hsk_level, lines
    If "lines" is provided, all existing lines are replaced with the new set.
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_passage(passage_id, data)
        return _ok(result, 200)
    except PassageServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/passage/<passage_id>
# ---------------------------------------------------------------------------
@passage_crud_bp.route("/<string:passage_id>", methods=["DELETE"])
def delete_passage_endpoint(passage_id: str):
    """Delete a passage and all its lines (cascade)."""
    try:
        result = delete_passage(passage_id)
        return _ok(result, 200)
    except PassageServiceError as exc:
        return _handle_service_error(exc)
