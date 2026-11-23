"""
Role-based guard on the /api/admin blueprints and the role/permission data in
the auth responses. Follows the suite's no-conftest conventions: a fresh Flask
app per fixture, the permission lookup monkeypatched so no DB is touched.
"""
import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask, jsonify
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.auth import auth_routes, permissions
from routes.auth.auth_routes import auth_bp
from routes.user.user_crud_routes import user_crud_bp
from routes.vocab.vocab_crud_routes import vocab_crud_bp

ADMIN_PERMS = frozenset({"manage:access", "user:read", "user:write", "user:delete", "vocab:read"})
PASSWORD = "correct-horse"


def _row(id, username, role):
    return {
        "id": id, "username": username, "email": f"{username}@example.com",
        "password": generate_password_hash(PASSWORD), "level": 1, "avatar_path": None,
        "hanzi_font": None, "hanzi_script": None, "ui_language": None, "role": role,
    }


ROWS = {"root": _row(1, "root", "admin"), "kid": _row(2, "kid", "student")}
BY_ID = {str(r["id"]): r for r in ROWS.values()}


@pytest.fixture
def client(monkeypatch):
    perms = {"admin": ADMIN_PERMS, "student": frozenset()}
    monkeypatch.setattr(permissions, "get_permissions", lambda role: perms.get(role, frozenset()))
    monkeypatch.setattr(auth_routes, "get_permissions", lambda role: perms.get(role, frozenset()))
    monkeypatch.setattr(auth_routes, "avatar_url", lambda path: None)
    monkeypatch.setattr(auth_routes, "get_user_by_username", ROWS.get)
    monkeypatch.setattr(auth_routes, "get_user_by_id", lambda uid: auth_routes._build_user(BY_ID[str(uid)]) if str(uid) in BY_ID else None)

    app = Flask(__name__)
    app.secret_key = "test"
    app.testing = True
    lm = LoginManager()
    lm.init_app(app)
    lm.user_loader(auth_routes.get_user_by_id)

    @lm.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "error": "Authentication required."}), 401

    for bp in (auth_bp, user_crud_bp, vocab_crud_bp):
        app.register_blueprint(bp)
    with app.test_client() as c:
        yield c


def _login(client, username):
    resp = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.get_json()["data"]


def test_login_returns_role_and_sorted_permissions(client):
    data = _login(client, "root")
    assert data["role"] == "admin"
    assert data["permissions"] == sorted(ADMIN_PERMS)


def test_student_login_has_no_permissions(client):
    data = _login(client, "kid")
    assert data["role"] == "student"
    assert data["permissions"] == []


def test_me_includes_role(client):
    _login(client, "root")
    assert client.get("/api/auth/me").get_json()["data"]["role"] == "admin"


def test_admin_endpoint_rejects_signed_out_with_401(client):
    assert client.post("/api/admin/user/query", json={}).status_code == 401


def test_admin_endpoint_rejects_student_with_403(client):
    _login(client, "kid")
    resp = client.post("/api/admin/user/query", json={})
    assert resp.status_code == 403
    assert resp.get_json()["success"] is False


def test_admin_query_allowed_with_read_permission(client):
    _login(client, "root")
    with patch("routes.user.user_crud_routes.list_users", return_value={"items": []}):
        assert client.post("/api/admin/user/query", json={}).status_code == 200


def test_missing_write_permission_blocks_post_but_not_read(client):
    # The admin fixture role holds vocab:read only.
    _login(client, "root")
    with patch("routes.vocab.vocab_crud_routes.get_vocab", return_value={"id": 1}):
        assert client.get("/api/admin/vocab/1").status_code == 200
    assert client.post("/api/admin/vocab", json={"cn": "x"}).status_code == 403
    assert client.delete("/api/admin/vocab/1").status_code == 403


def test_admin_cannot_change_own_role(client):
    _login(client, "root")
    resp = client.put("/api/admin/user/1", json={"role": "student"})
    assert resp.status_code == 400
    assert "own role" in resp.get_json()["error"]


def test_admin_can_resubmit_own_unchanged_role(client):
    _login(client, "root")
    with patch("routes.user.user_crud_routes.update_user", return_value={"id": 1, "role": "admin"}):
        resp = client.put("/api/admin/user/1", json={"role": "admin", "level": 3})
    assert resp.status_code == 200


def test_admin_can_change_another_users_role(client):
    _login(client, "root")
    with patch("routes.user.user_crud_routes.update_user", return_value={"id": 2, "role": "admin"}) as upd:
        resp = client.put("/api/admin/user/2", json={"role": "admin"})
    assert resp.status_code == 200
    upd.assert_called_once_with(2, {"role": "admin"})


@pytest.mark.parametrize("method,path,expected", [
    ("GET", "/x", "read"),
    ("POST", "/api/admin/user/query", "read"),
    ("POST", "/api/admin/user", "write"),
    ("PUT", "/api/admin/user/1", "write"),
    ("DELETE", "/api/admin/user/1", "delete"),
])
def test_action_for_request(method, path, expected):
    app = Flask(__name__)
    with app.test_request_context(path, method=method):
        assert permissions.action_for_request() == expected
