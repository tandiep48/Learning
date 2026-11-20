"""
Student support tickets (/api/support) and the staff inbox (/api/admin/support).
No-conftest conventions: fresh Flask app per fixture, services patched, no DB.
"""
import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask, jsonify
from flask_login import LoginManager, UserMixin, login_user

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.support.service import SupportServiceError
from routes.auth import permissions
from routes.support.support_admin_routes import support_admin_bp
from routes.support.support_routes import support_bp

TICKET = {"id": 5, "user_id": 7, "subject": "Typo", "status": "open"}


class FakeUser(UserMixin):
    def __init__(self, id, role):
        self.id = id
        self.role = role


USERS = {"7": FakeUser(7, "student"), "1": FakeUser(1, "editor")}


@pytest.fixture
def client(monkeypatch):
    perms = {"editor": frozenset({"support:read", "support:write"}), "student": frozenset()}
    monkeypatch.setattr(permissions, "get_permissions", lambda role: perms.get(role, frozenset()))

    app = Flask(__name__)
    app.secret_key = "test"
    app.testing = True
    lm = LoginManager()
    lm.init_app(app)
    lm.user_loader(lambda uid: USERS.get(str(uid)))

    @lm.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "error": "Authentication required."}), 401

    @app.route("/_login/<uid>")
    def _login(uid):
        login_user(USERS[uid])
        return "ok"

    app.register_blueprint(support_bp)
    app.register_blueprint(support_admin_bp)
    with app.test_client() as c:
        yield c


def _as(client, uid):
    client.get(f"/_login/{uid}")


# --- student endpoints -----------------------------------------------------

def test_student_endpoints_require_login(client):
    assert client.post("/api/support/tickets", json={}).status_code == 401
    assert client.get("/api/support/tickets/1").status_code == 401


def test_create_ticket_uses_session_user_and_validated_body(client):
    _as(client, "7")
    with patch("routes.support.support_routes.create_ticket", return_value=TICKET) as create:
        resp = client.post("/api/support/tickets", json={
            "subject": "Typo", "body": "Wrong pinyin", "item_type": "vocab", "item_id": "42",
        })
    assert resp.status_code == 201
    create.assert_called_once_with(7, {
        "subject": "Typo", "body": "Wrong pinyin", "item_type": "vocab", "item_id": "42", "page_url": None,
    })


@pytest.mark.parametrize("payload", [
    {"subject": "", "body": "x"},
    {"subject": "s", "body": "   "},
    {"subject": "s", "body": "x", "item_type": "users"},
    {"subject": "s", "body": "x", "role": "admin"},
    {"subject": "s", "body": "x" * 2001},
])
def test_create_ticket_rejects_bad_input(client, payload):
    _as(client, "7")
    assert client.post("/api/support/tickets", json=payload).status_code == 422


def test_my_tickets_are_scoped_to_the_user(client):
    _as(client, "7")
    with patch("routes.support.support_routes.list_my_tickets", return_value={"items": []}) as lst:
        assert client.post("/api/support/tickets/query", json={}).status_code == 200
    lst.assert_called_once_with(7, 1, 20)


def test_get_ticket_passes_owner_and_maps_404(client):
    _as(client, "7")
    with patch("routes.support.support_routes.get_ticket", side_effect=SupportServiceError("nope", 404)) as get:
        resp = client.get("/api/support/tickets/9")
    assert resp.status_code == 404
    get.assert_called_once_with(9, owner_id=7)


def test_student_reply_is_not_staff(client):
    _as(client, "7")
    with patch("routes.support.support_routes.add_message", return_value={"id": 1}) as add:
        resp = client.post("/api/support/tickets/5/messages", json={"body": "thanks"})
    assert resp.status_code == 201
    add.assert_called_once_with(5, 7, "thanks", is_staff=False)


# --- staff endpoints -------------------------------------------------------

def test_inbox_blocks_students_and_signed_out(client):
    assert client.post("/api/admin/support/query", json={}).status_code == 401
    _as(client, "7")
    assert client.post("/api/admin/support/query", json={}).status_code == 403


def test_inbox_query_passes_filters(client):
    _as(client, "1")
    with patch("routes.support.support_admin_routes.list_tickets", return_value={"items": []}) as lst:
        resp = client.post("/api/admin/support/query", json={"status": "open", "search": " bob "})
    assert resp.status_code == 200
    lst.assert_called_once_with(1, 20, "open", "bob")


def test_staff_reply_is_flagged_staff(client):
    _as(client, "1")
    with patch("routes.support.support_admin_routes.add_message", return_value={"id": 2}) as add:
        resp = client.post("/api/admin/support/5/messages", json={"body": "fixed"})
    assert resp.status_code == 201
    add.assert_called_once_with(5, 1, "fixed", is_staff=True)


def test_update_only_sends_provided_keys(client):
    _as(client, "1")
    with patch("routes.support.support_admin_routes.update_ticket", return_value=TICKET) as upd:
        assert client.put("/api/admin/support/5", json={"status": "resolved"}).status_code == 200
        client.put("/api/admin/support/5", json={"assignee_id": 0})
    assert upd.call_args_list[0].args == (5, {"status": "resolved"})
    assert upd.call_args_list[1].args == (5, {"assignee_id": 0})


def test_update_rejects_unknown_status(client):
    _as(client, "1")
    assert client.put("/api/admin/support/5", json={"status": "closed"}).status_code == 422
