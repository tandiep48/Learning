"""
Learn Together socket handshake auth: the `connect` handler must accept a web
client's Flask-Login session, accept a mobile client's signed bearer token (via
the socket.io `auth` option or an Authorization header) and reject an anonymous
handshake.

Follows the suite's no-conftest conventions: a fresh Flask + SocketIO app per
fixture with only the login manager and the competition socket wired, the user
lookup monkeypatched so no DB is touched, and real itsdangerous tokens so
signing/expiry is exercised end-to-end.
"""
import os
import sys

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import routes.auth as routes_auth
from routes.auth import auth_routes
from service import competition_socket, token_service

SECRET = "test-secret"
USER = auth_routes.User(7, "learner", "learner@example.com", 1)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(
        routes_auth, "get_user_by_id",
        lambda user_id: USER if str(user_id) == str(USER.id) else None,
    )

    app = Flask(__name__)
    app.secret_key = SECRET

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.user_loader(lambda uid: USER if str(uid) == str(USER.id) else None)

    socketio = SocketIO(app, async_mode="threading")
    competition_socket.init_competition_socket(socketio)
    app.config["_socketio"] = socketio
    return app


def _mint_token(user_id=USER.id):
    app = Flask(__name__)
    app.secret_key = SECRET
    with app.app_context():
        return token_service.generate_auth_token(user_id)


def test_valid_bearer_token_in_auth_connects(app):
    socketio = app.config["_socketio"]
    client = socketio.test_client(app, auth={"token": _mint_token()})
    assert client.is_connected()


def test_valid_bearer_token_in_header_connects(app):
    socketio = app.config["_socketio"]
    client = socketio.test_client(
        app, headers={"Authorization": f"Bearer {_mint_token()}"}
    )
    assert client.is_connected()


def test_anonymous_handshake_is_rejected(app):
    socketio = app.config["_socketio"]
    client = socketio.test_client(app)
    assert not client.is_connected()


def test_tampered_token_is_rejected(app):
    socketio = app.config["_socketio"]
    client = socketio.test_client(app, auth={"token": f"{_mint_token()}x"})
    assert not client.is_connected()
