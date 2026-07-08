"""
routes/passage_vocab_crud_routes.py
------------------------------------
CRUD API Blueprint for the `passage_vocabulary` join table — the vocabulary
words that appear inside a given passage.

All endpoints are publicly accessible (no @login_required).

Prefix: /api/admin/passage/<passage_id>/vocabulary

Endpoints:
    GET    /api/admin/passage/<passage_id>/vocabulary        → list linked words (with details)
    POST   /api/admin/passage/<passage_id>/vocabulary        → link a word   (body: {"cn": "你好"})
    DELETE /api/admin/passage/<passage_id>/vocabulary/<cn>   → unlink a word
"""

from flask import Blueprint, request, jsonify

from service.passage_vocabulary_service import (
    PassageVocabularyServiceError,
    list_passage_vocab,
    add_passage_vocab,
    remove_passage_vocab,
)

passage_vocab_crud_bp = Blueprint(
    "passage_vocab_crud",
    __name__,
    url_prefix="/api/admin/passage/<string:passage_id>/vocabulary",
)


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _handle_service_error(exc: PassageVocabularyServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>/vocabulary
# ---------------------------------------------------------------------------
@passage_vocab_crud_bp.route("", methods=["GET"])
def list_passage_vocab_endpoint(passage_id: str):
    """List all vocabulary words linked to a passage."""
    try:
        result = list_passage_vocab(passage_id)
        return jsonify(result), 200
    except PassageVocabularyServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/passage/<passage_id>/vocabulary
# Body (JSON): { "cn": "你好" }
# ---------------------------------------------------------------------------
@passage_vocab_crud_bp.route("", methods=["POST"])
def add_passage_vocab_endpoint(passage_id: str):
    """Link an existing vocabulary word to a passage."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = add_passage_vocab(passage_id, data.get("cn", ""))
        return jsonify(result), 201
    except PassageVocabularyServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/passage/<passage_id>/vocabulary/<cn>
# ---------------------------------------------------------------------------
@passage_vocab_crud_bp.route("/<string:cn>", methods=["DELETE"])
def remove_passage_vocab_endpoint(passage_id: str, cn: str):
    """Remove the link between a passage and a vocabulary word."""
    try:
        result = remove_passage_vocab(passage_id, cn)
        return jsonify(result), 200
    except PassageVocabularyServiceError as exc:
        return _handle_service_error(exc)
