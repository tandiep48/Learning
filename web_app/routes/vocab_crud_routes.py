"""
routes/vocab_crud_routes.py
-----------------------------
CRUD API Blueprint for the `vocabulary` table.

All endpoints are publicly accessible (no @login_required).

Prefix: /api/admin/vocab

Endpoints:
    GET    /api/admin/vocab                  → list (paginated)
    GET    /api/admin/vocab/<int:vocab_id>   → get single
    POST   /api/admin/vocab                  → create
    PUT    /api/admin/vocab/<int:vocab_id>   → update
    DELETE /api/admin/vocab/<int:vocab_id>   → delete
"""

from flask import Blueprint, request, jsonify

from service.vocab_service import (
    VocabServiceError,
    list_vocab,
    get_vocab,
    create_vocab,
    update_vocab,
    delete_vocab,
)

vocab_crud_bp = Blueprint("vocab_crud", __name__, url_prefix="/api/admin/vocab")


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _handle_service_error(exc: VocabServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/vocab
# Query params: page, page_size, hsk_level
# ---------------------------------------------------------------------------
@vocab_crud_bp.route("", methods=["GET"])
def list_vocab_endpoint():
    """List vocabulary entries with optional HSK level filter and pagination."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        return _error("'page' and 'page_size' must be integers.", 400)

    hsk_level = request.args.get("hsk_level") or None
    search = request.args.get("search") or None
    result = list_vocab(page=page, page_size=page_size, hsk_level=hsk_level, search=search)
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/admin/vocab/<vocab_id>
# ---------------------------------------------------------------------------
@vocab_crud_bp.route("/<int:vocab_id>", methods=["GET"])
def get_vocab_endpoint(vocab_id: int):
    """Get a single vocabulary entry by its numeric ID."""
    try:
        result = get_vocab(vocab_id)
        return jsonify(result), 200
    except VocabServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/vocab
# Body (JSON):
#   { "cn": "你好", "pinyin": "nǐ hǎo", "meaning_en": "Hello",
#     "meaning_vn": "Xin chào", "hsk_level": "HSK1",
#     "audio_key": "...", "source": "..." }
# ---------------------------------------------------------------------------
@vocab_crud_bp.route("", methods=["POST"])
def create_vocab_endpoint():
    """Create a new vocabulary entry. Required: cn."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = create_vocab(data)
        return jsonify(result), 201
    except VocabServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/vocab/<vocab_id>
# Body (JSON): any subset of vocab fields to update
# ---------------------------------------------------------------------------
@vocab_crud_bp.route("/<int:vocab_id>", methods=["PUT"])
def update_vocab_endpoint(vocab_id: int):
    """Update an existing vocabulary entry. Send only fields you want to change."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_vocab(vocab_id, data)
        return jsonify(result), 200
    except VocabServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/vocab/<vocab_id>
# ---------------------------------------------------------------------------
@vocab_crud_bp.route("/<int:vocab_id>", methods=["DELETE"])
def delete_vocab_endpoint(vocab_id: int):
    """Delete a vocabulary entry by its numeric ID."""
    try:
        result = delete_vocab(vocab_id)
        return jsonify(result), 200
    except VocabServiceError as exc:
        return _handle_service_error(exc)
