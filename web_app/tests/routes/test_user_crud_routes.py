import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.user.user_crud_routes import user_crud_bp
from entity.user.service import UserServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(user_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


USER_DICT = {"id": 1, "username": "alice", "email": "alice@example.com", "level": 1}


# ---------------------------------------------------------------------------
# GET /api/admin/user
# ---------------------------------------------------------------------------

def test_list_users_endpoint(client):
    with patch("routes.user.user_crud_routes.list_users", return_value={
        "items": [USER_DICT], "page": 1, "page_size": 20, "total": 1, "total_pages": 1
    }) as mock_list:
        resp = client.get("/api/admin/user?page=1&page_size=20&search=alice")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["items"][0]["username"] == "alice"
    assert "password" not in body["data"]["items"][0]
    mock_list.assert_called_once_with(page=1, page_size=20, search="alice")


def test_list_users_endpoint_rejects_non_integer_paging(client):
    resp = client.get("/api/admin/user?page=abc")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


# ---------------------------------------------------------------------------
# GET /api/admin/user/<user_id>
# ---------------------------------------------------------------------------

def test_get_user_endpoint_found(client):
    with patch("routes.user.user_crud_routes.get_user", return_value=USER_DICT):
        resp = client.get("/api/admin/user/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == 1


def test_get_user_endpoint_not_found(client):
    with patch("routes.user.user_crud_routes.get_user",
               side_effect=UserServiceError("User with id=999 not found.", 404)):
        resp = client.get("/api/admin/user/999")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/user
# ---------------------------------------------------------------------------

def test_create_user_endpoint_success(client):
    with patch("routes.user.user_crud_routes.create_user", return_value=USER_DICT):
        resp = client.post("/api/admin/user", json={
            "username": "alice", "email": "alice@example.com", "password": "secret123"
        })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["username"] == "alice"


def test_create_user_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/user", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_create_user_endpoint_duplicate_username(client):
    with patch("routes.user.user_crud_routes.create_user",
               side_effect=UserServiceError("Username 'alice' is already taken.", 409)):
        resp = client.post("/api/admin/user", json={
            "username": "alice", "email": "alice@example.com", "password": "secret123"
        })

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["success"] is False
    assert "already taken" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/user/<user_id>
# ---------------------------------------------------------------------------

def test_update_user_endpoint_success(client):
    updated = {**USER_DICT, "level": 2}
    with patch("routes.user.user_crud_routes.update_user", return_value=updated):
        resp = client.put("/api/admin/user/1", json={"level": 2})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["level"] == 2


def test_update_user_endpoint_not_found(client):
    with patch("routes.user.user_crud_routes.update_user",
               side_effect=UserServiceError("User with id=999 not found.", 404)):
        resp = client.put("/api/admin/user/999", json={"level": 2})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_update_user_endpoint_rejects_non_json_body(client):
    resp = client.put("/api/admin/user/1", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/user/<user_id>
# ---------------------------------------------------------------------------

def test_delete_user_endpoint_success(client):
    with patch("routes.user.user_crud_routes.delete_user",
               return_value={"message": "User id=1 deleted successfully."}):
        resp = client.delete("/api/admin/user/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_user_endpoint_not_found(client):
    with patch("routes.user.user_crud_routes.delete_user",
               side_effect=UserServiceError("User with id=999 not found.", 404)):
        resp = client.delete("/api/admin/user/999")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
