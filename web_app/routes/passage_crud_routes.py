"""
routes/passage_crud_routes.py
-------------------------------
CRUD API Blueprint for `lesson_passages` + `lesson_lines`.

All endpoints are publicly accessible (no @login_required).

Prefix: /api/admin/passage

Endpoints:
    GET    /api/admin/passage                    → list passages (paginated, no lines)
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

from service.passage_service import (
    PassageServiceError,
    list_passages,
    get_passage,
    create_passage,
    update_passage,
    delete_passage,
)

passage_crud_bp = Blueprint("passage_crud", __name__, url_prefix="/api/admin/passage")


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _handle_service_error(exc: PassageServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/passage
# Query params: page, page_size, hsk_level
# ---------------------------------------------------------------------------
@passage_crud_bp.route("", methods=["GET"])
def list_passages_endpoint():
    """List lesson passages with optional HSK level filter. Lines are NOT included."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        return _error("'page' and 'page_size' must be integers.", 400)

    hsk_level = request.args.get("hsk_level") or None
    result = list_passages(page=page, page_size=page_size, hsk_level=hsk_level)
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>
# ---------------------------------------------------------------------------
@passage_crud_bp.route("/<string:passage_id>", methods=["GET"])
def get_passage_endpoint(passage_id: str):
    """Get a single passage with all its lines."""
    try:
        result = get_passage(passage_id)
        return jsonify(result), 200
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
        return jsonify(result), 201
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
        return jsonify(result), 200
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
        return jsonify(result), 200
    except PassageServiceError as exc:
        return _handle_service_error(exc)
