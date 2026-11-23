"""
routes/user_crud_routes.py
----------------------------
CRUD API Blueprint for the `users` table (admin management).

Every endpoint requires the matching user:read|write|delete permission (see
routes.auth.permissions). Password hashes are never returned.

Prefix: /api/admin/user

Endpoints:
    GET    /api/admin/user/roles            → role names (for the role dropdown)
    POST   /api/admin/user/query            → list (paginated, validated body, optional search)
    GET    /api/admin/user/<int:user_id>    → get single
    POST   /api/admin/user                  → create
    PUT    /api/admin/user/<int:user_id>    → update
    DELETE /api/admin/user/<int:user_id>    → delete
"""

from flask import Blueprint, request, jsonify
from flask_login import current_user

from entity.user.service import (
    UserServiceError,
    list_users,
    get_user,
    create_user,
    update_user,
    delete_user,
)
from entity.role.service import list_roles
from entity.user.schemas import UserQuery
from routes.validation import parse_body, RequestValidationError
from routes.auth.permissions import guard_admin_blueprint

user_crud_bp = Blueprint("user_crud", __name__, url_prefix="/api/admin/user")
guard_admin_blueprint(user_crud_bp, "user")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: UserServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# POST /api/admin/user/query
# Body (JSON): { "page": 1, "page_size": 20, "search": "alice" }  (all optional)
# Replaces the former GET list — search now travels in a validated body.
# ---------------------------------------------------------------------------
@user_crud_bp.route("/query", methods=["POST"])
def query_users_endpoint():
    """List users from a validated JSON body (optional username/email search)."""
    try:
        params = parse_body(UserQuery)
    except RequestValidationError as exc:
        return exc.response()

    result = list_users(page=params.page, page_size=params.page_size, search=params.search)
    return _ok(result, 200)


# ---------------------------------------------------------------------------
# GET /api/admin/user/roles
# ---------------------------------------------------------------------------
@user_crud_bp.route("/roles", methods=["GET"])
def list_roles_endpoint():
    """List the role names a user can be assigned."""
    return _ok(list_roles(), 200)


# ---------------------------------------------------------------------------
# GET /api/admin/user/<user_id>
# ---------------------------------------------------------------------------
@user_crud_bp.route("/<int:user_id>", methods=["GET"])
def get_user_endpoint(user_id: int):
    """Get a single user by numeric ID."""
    try:
        result = get_user(user_id)
        return _ok(result, 200)
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
        return _ok(result, 201)
    except UserServiceError as exc:
        return _handle_service_error(exc)


# ---------------------------------------------------------------------------
# PUT /api/admin/user/<user_id>
# Body (JSON): any subset of { username, email, password, level, role }
# ---------------------------------------------------------------------------
@user_crud_bp.route("/<int:user_id>", methods=["PUT"])
def update_user_endpoint(user_id: int):
    """Update an existing user. Send only the fields you want to change."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)
    if (
        "role" in data
        and str(current_user.get_id()) == str(user_id)
        and data["role"] != current_user.role
    ):
        return _error("You cannot change your own role.", 400)
    try:
        result = update_user(user_id, data)
        return _ok(result, 200)
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
        return _ok(result, 200)
    except UserServiceError as exc:
        return _handle_service_error(exc)
