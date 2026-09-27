"""
routes/vocab_crud_routes.py
-----------------------------
CRUD API Blueprint for the `vocabulary` table.

All endpoints are publicly accessible (no @login_required).

Prefix: /api/admin/vocab

Endpoints:
    POST   /api/admin/vocab/query            → list (paginated, validated body)
    GET    /api/admin/vocab/<int:vocab_id>   → get single
    POST   /api/admin/vocab                  → create
    PUT    /api/admin/vocab/<int:vocab_id>   → update
    DELETE /api/admin/vocab/<int:vocab_id>   → delete
"""

from flask import Blueprint, request, jsonify

from entity.vocabulary.service import (
    VocabServiceError,
    list_vocab,
    get_vocab,
    create_vocab,
    update_vocab,
    delete_vocab,
)
from entity.vocabulary.schemas import VocabQuery
from routes.validation import parse_body, RequestValidationError

vocab_crud_bp = Blueprint("vocab_crud", __name__, url_prefix="/api/admin/vocab")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: VocabServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# POST /api/admin/vocab/query
# Body (JSON): { "page": 1, "page_size": 20, "hsk_level": "HSK1", "search": "hao" }
# All fields optional. Replaces the former GET list — the filter now travels in a
# validated JSON body instead of the query string.
# ---------------------------------------------------------------------------
@vocab_crud_bp.route("/query", methods=["POST"])
def query_vocab_endpoint():
    """List vocabulary entries from a validated JSON body (filter + pagination)."""
    try:
        params = parse_body(VocabQuery)
    except RequestValidationError as exc:
        return exc.response()

    result = list_vocab(
        page=params.page,
        page_size=params.page_size,
        hsk_level=params.hsk_level,
        search=params.search,
    )
    return _ok(result, 200)


# ---------------------------------------------------------------------------
# GET /api/admin/vocab/<vocab_id>
# ---------------------------------------------------------------------------
@vocab_crud_bp.route("/<int:vocab_id>", methods=["GET"])
def get_vocab_endpoint(vocab_id: int):
    """Get a single vocabulary entry by its numeric ID."""
    try:
        result = get_vocab(vocab_id)
        return _ok(result, 200)
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
        return _ok(result, 201)
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
        return _ok(result, 200)
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
        return _ok(result, 200)
    except VocabServiceError as exc:
        return _handle_service_error(exc)
