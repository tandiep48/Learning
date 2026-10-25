"""
Mobile bearer-token auth: the `/api/auth/token` endpoint and the
`request_loader` hook that lets @login_required routes accept the token.

Follows the suite's no-conftest conventions: a fresh Flask app per fixture,
only the pieces under test registered, and the user lookups monkeypatched so
no DB is touched. Credentials go through the real `check_password_hash`, and
tokens through the real itsdangerous serializer, so signing/expiry is
exercised end-to-end rather than mocked.
"""
import os
import sys

import pytest
from flask import Flask, jsonify
from flask_login import LoginManager, login_required
from werkzeug.security import generate_password_hash

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.auth import auth_routes
from service import token_service

SECRET = "test-secret"
PASSWORD = "correct-horse"
USER_ROW = {
    "id": 42,
    "username": "learner",
    "email": "learner@example.com",
    "password": generate_password_hash(PASSWORD),
    "level": 1,
    "avatar_path": None,
    "hanzi_font": None,
    "hanzi_script": None,
    "ui_language": None,
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        auth_routes, "get_user_by_username",
        lambda username: USER_ROW if username == "learner" else None,
    )
    monkeypatch.setattr(
        auth_routes, "get_user_by_id",
        lambda user_id: auth_routes._build_user(USER_ROW)
        if str(user_id) == str(USER_ROW["id"]) else None,
    )
    # avatar_url otherwise reaches gcs config; serialization only needs a value.
    monkeypatch.setattr(auth_routes, "avatar_url", lambda path: None)

    app = Flask(__name__)
    app.secret_key = SECRET

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.request_loader
    def load_user_from_token(req):
        header = req.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        user_id = token_service.load_auth_token(header[len("Bearer "):].strip())
        if user_id is None:
            return None
        return auth_routes.get_user_by_id(user_id)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "error": "Authentication required."}), 401

    @app.route("/protected")
    @login_required
    def protected():
        return jsonify({"success": True, "data": "secret"})

    app.register_blueprint(auth_routes.auth_bp)
    with app.test_client() as c:
        yield c


def _mint_token(user_id=USER_ROW["id"]):
    """Mint a token the way the app does, inside an app context on the same key."""
    app = Flask(__name__)
    app.secret_key = SECRET
    with app.app_context():
        return token_service.generate_auth_token(user_id)


# ── POST /api/auth/token ────────────────────────────────────────────────────
def test_token_valid_credentials_returns_token_and_user(client):
    resp = client.post("/api/auth/token", json={"username": "learner", "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert isinstance(body["data"]["token"], str) and body["data"]["token"]
    assert body["data"]["user"]["id"] == USER_ROW["id"]
    assert body["data"]["user"]["username"] == "learner"


def test_token_wrong_password_rejected(client):
    resp = client.post("/api/auth/token", json={"username": "learner", "password": "nope"})
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_token_unknown_user_rejected(client):
    resp = client.post("/api/auth/token", json={"username": "ghost", "password": PASSWORD})
    assert resp.status_code == 401


def test_token_missing_fields_rejected(client):
    resp = client.post("/api/auth/token", json={"username": "learner"})
    assert resp.status_code == 400


# ── request_loader: @login_required routes accept the bearer token ───────────
def test_valid_token_authenticates_protected_route(client):
    resp = client.get("/protected", headers={"Authorization": f"Bearer {_mint_token()}"})
    assert resp.status_code == 200
    assert resp.get_json()["data"] == "secret"


def test_missing_header_is_unauthorized(client):
    assert client.get("/protected").status_code == 401


def test_tampered_token_is_unauthorized(client):
    resp = client.get("/protected", headers={"Authorization": f"Bearer {_mint_token()}x"})
    assert resp.status_code == 401


def test_wrong_scheme_is_unauthorized(client):
    resp = client.get("/protected", headers={"Authorization": _mint_token()})
    assert resp.status_code == 401


def test_expired_token_rejected_at_route(client, monkeypatch):
    # Force any token to read as expired: age (>=0) always exceeds max_age=-1.
    real = token_service.load_auth_token
    monkeypatch.setattr(token_service, "load_auth_token", lambda t, max_age=-1: real(t, max_age=-1))
    resp = client.get("/protected", headers={"Authorization": f"Bearer {_mint_token()}"})
    assert resp.status_code == 401


# ── token_service unit: expiry / tamper handled, never raises ────────────────
def test_load_auth_token_round_trip():
    app = Flask(__name__)
    app.secret_key = SECRET
    with app.app_context():
        token = token_service.generate_auth_token(7)
        assert token_service.load_auth_token(token) == 7


def test_load_auth_token_expired_returns_none():
    app = Flask(__name__)
    app.secret_key = SECRET
    with app.app_context():
        token = token_service.generate_auth_token(7)
        assert token_service.load_auth_token(token, max_age=-1) is None


def test_load_auth_token_bad_input_returns_none():
    app = Flask(__name__)
    app.secret_key = SECRET
    with app.app_context():
        assert token_service.load_auth_token("") is None
        assert token_service.load_auth_token("garbage.token.value") is None
