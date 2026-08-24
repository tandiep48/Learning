import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.book_crud_routes import book_crud_bp
from entity.book.service import BookServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(book_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/admin/book
# ---------------------------------------------------------------------------

def test_list_books_endpoint(client):
    with patch("routes.book_crud_routes.list_books", return_value=[
        {"book_code": "AML", "name_en": "A Month in Life", "name_vn": "Mot thang"}
    ]):
        resp = client.get("/api/admin/book")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"][0]["book_code"] == "AML"


# ---------------------------------------------------------------------------
# GET /api/admin/book/<book_code>
# ---------------------------------------------------------------------------

def test_get_book_endpoint_found(client):
    with patch("routes.book_crud_routes.get_book",
               return_value={"book_code": "AML", "name_en": "A Month in Life", "name_vn": "Mot thang"}):
        resp = client.get("/api/admin/book/AML")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["book_code"] == "AML"


def test_get_book_endpoint_not_found(client):
    with patch("routes.book_crud_routes.get_book",
               side_effect=BookServiceError("Book 'MISSING' not found.", 404)):
        resp = client.get("/api/admin/book/MISSING")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/book
# ---------------------------------------------------------------------------

def test_create_book_endpoint_success(client):
    with patch("routes.book_crud_routes.create_book",
               return_value={"book_code": "AML", "name_en": "A Month in Life", "name_vn": None}):
        resp = client.post("/api/admin/book", json={"book_code": "AML", "name_en": "A Month in Life"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["book_code"] == "AML"


def test_create_book_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/book", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_create_book_endpoint_service_error(client):
    with patch("routes.book_crud_routes.create_book",
               side_effect=BookServiceError("Book 'AML' already exists. Use PUT to update it.")):
        resp = client.post("/api/admin/book", json={"book_code": "AML"})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "already exists" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/book/<book_code>
# ---------------------------------------------------------------------------

def test_update_book_endpoint_success(client):
    with patch("routes.book_crud_routes.update_book",
               return_value={"book_code": "AML", "name_en": "Updated", "name_vn": None}):
        resp = client.put("/api/admin/book/AML", json={"name_en": "Updated"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["name_en"] == "Updated"


def test_update_book_endpoint_not_found(client):
    with patch("routes.book_crud_routes.update_book",
               side_effect=BookServiceError("Book 'MISSING' not found.", 404)):
        resp = client.put("/api/admin/book/MISSING", json={"name_en": "X"})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/book/<book_code>
# ---------------------------------------------------------------------------

def test_delete_book_endpoint_success(client):
    with patch("routes.book_crud_routes.delete_book",
               return_value={"message": "Book 'AML' deleted successfully."}):
        resp = client.delete("/api/admin/book/AML")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_book_endpoint_not_found(client):
    with patch("routes.book_crud_routes.delete_book",
               side_effect=BookServiceError("Book 'MISSING' not found.", 404)):
        resp = client.delete("/api/admin/book/MISSING")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
