"""
routes/auth/permissions.py
--------------------------
Permission checks for the admin (manage) API.

`guard_admin_blueprint(bp, resource)` makes every route on `bp` require a
signed-in user whose role holds `<resource>:read|write|delete`:

    GET, POST .../query  -> read
    DELETE               -> delete
    any other POST/PUT/PATCH -> write

Signed-out requests get 401, signed-in users lacking the permission get 403.
"""

from flask import jsonify, request
from flask_login import current_user

from entity.role.service import get_permissions

READ, WRITE, DELETE = "read", "write", "delete"


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def action_for_request() -> str:
    """Map the current request to the permission action it needs."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return READ
    if request.method == "DELETE":
        return DELETE
    if request.method == "POST" and request.path.rstrip("/").endswith("/query"):
        return READ
    return WRITE


def check_permission(permission: str):
    """Return None when the current user holds `permission`, else a 401/403 response."""
    if not current_user.is_authenticated:
        return _error("Authentication required.", 401)
    if permission not in get_permissions(getattr(current_user, "role", None)):
        return _error("You do not have permission to do that.", 403)
    return None


def guard_admin_blueprint(bp, resource: str) -> None:
    """Require `<resource>:<action>` on every request handled by `bp`."""

    @bp.before_request
    def _require_resource_permission():
        # CORS preflights carry no credentials; flask-cors answers them.
        if request.method == "OPTIONS":
            return None
        return check_permission(f"{resource}:{action_for_request()}")
