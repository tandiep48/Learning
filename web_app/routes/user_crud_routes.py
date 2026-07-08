"""
routes/user_crud_routes.py
----------------------------
CRUD API Blueprint for the `users` table (admin management).

All endpoints are publicly accessible (no @login_required), matching the
other /api/admin CRUD blueprints. Password hashes are never returned.

Prefix: /api/admin/user

Endpoints:
    GET    /api/admin/user                  → list (paginated, optional ?search=)
    GET    /api/admin/user/<int:user_id>    → get single
    POST   /api/admin/user                  → create
    PUT    /api/admin/user/<int:user_id>    → update
    DELETE /api/admin/user/<int:user_id>    → delete
"""

from flask import Blueprint, request, jsonify

from service.user_service import (
    UserServiceError,
    list_users,
    get_user,
    create_user,
    update_user,
    delete_user,
)

user_crud_bp = Blueprint("user_crud", __name__, url_prefix="/api/admin/user")


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _handle_service_error(exc: UserServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/admin/user
# Query params: page, page_size, search
# ---------------------------------------------------------------------------
@user_crud_bp.route("", methods=["GET"])
def list_users_endpoint():
    """List users with optional search (username/email) and pagination."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        return _error("'page' and 'page_size' must be integers.", 400)

    search = request.args.get("search") or None
    result = list_users(page=page, page_size=page_size, search=search)
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/admin/user/<user_id>
# ---------------------------------------------------------------------------
@user_crud_bp.route("/<int:user_id>", methods=["GET"])
def get_user_endpoint(user_id: int):
    """Get a single user by numeric ID."""
    try:
        result = get_user(user_id)
        return jsonify(result), 200
    except UserServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# POST /api/admin/user
# Body (JSON): { "username": "...", "email": "...", "password": "...", "level": 1 }
# ---------------------------------------------------------------------------
@user_crud_bp.route("", methods=["POST"])
def create_user_endpoint():
    """Create a new user. Required: username, email, password."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = create_user(data)
        return jsonify(result), 201
    except UserServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/user/<user_id>
# Body (JSON): any subset of { username, email, password, level }
# ---------------------------------------------------------------------------
@user_crud_bp.route("/<int:user_id>", methods=["PUT"])
def update_user_endpoint(user_id: int):
    """Update an existing user. Send only the fields you want to change."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    try:
        result = update_user(user_id, data)
        return jsonify(result), 200
    except UserServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# DELETE /api/admin/user/<user_id>
# ---------------------------------------------------------------------------
@user_crud_bp.route("/<int:user_id>", methods=["DELETE"])
def delete_user_endpoint(user_id: int):
    """Delete a user by numeric ID."""
    try:
        result = delete_user(user_id)
        return jsonify(result), 200
    except UserServiceError as exc:
        return _handle_service_error(exc)
