"""
routes/book_crud_routes.py
----------------------------
CRUD API Blueprint for `books`.

All endpoints are publicly accessible (no @login_required).

Prefix: /api/admin/book

Endpoints:
    GET    /api/admin/book                 -> list all books
    GET    /api/admin/book/<book_code>      -> get a single book
    POST   /api/admin/book                 -> create a book
    PUT    /api/admin/book/<book_code>      -> update a book
    DELETE /api/admin/book/<book_code>      -> delete a book

Example POST body:
    {
        "book_code": "AML",
        "name_en": "A Month in Life",
        "name_vn": "Mot thang"
    }
"""

from flask import Blueprint, request, jsonify

from entity.book.service import (
    BookServiceError,
    list_books,
    get_book,
    create_book,
    update_book,
    delete_book,
)

book_crud_bp = Blueprint("book_crud", __name__, url_prefix="/api/admin/book")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: BookServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/book
# ---------------------------------------------------------------------------
@book_crud_bp.route("", methods=["GET"])
def list_books_endpoint():
    """List all books."""
    result = list_books()
    return _ok(result, 200)


# ---------------------------------------------------------------------------
# GET /api/admin/book/<book_code>
# ---------------------------------------------------------------------------
@book_crud_bp.route("/<string:book_code>", methods=["GET"])
def get_book_endpoint(book_code: str):
    """Get a single book."""
    try:
        result = get_book(book_code)
        return _ok(result, 200)
    except BookServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/book
# ---------------------------------------------------------------------------
@book_crud_bp.route("", methods=["POST"])
def create_book_endpoint():
    """
    Create a new book.

    Required: book_code
    Optional: name_en, name_vn
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = create_book(data)
        return _ok(result, 201)
    except BookServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/book/<book_code>
# ---------------------------------------------------------------------------
@book_crud_bp.route("/<string:book_code>", methods=["PUT"])
def update_book_endpoint(book_code: str):
    """
    Update an existing book.

    Allowed fields: name_en, name_vn
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_book(book_code, data)
        return _ok(result, 200)
    except BookServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/book/<book_code>
# ---------------------------------------------------------------------------
@book_crud_bp.route("/<string:book_code>", methods=["DELETE"])
def delete_book_endpoint(book_code: str):
    """Delete a book."""
    try:
        result = delete_book(book_code)
        return _ok(result, 200)
    except BookServiceError as exc:
        return _handle_service_error(exc)
