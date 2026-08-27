import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.passage_line.passage_line_crud_routes import passage_line_crud_bp
from entity.passage.service import PassageServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(passage_line_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


LINE_DICT = {
    "id": 1, "passage_id": "H1_1_1", "line_id": 1, "speaker": "A", "content": "你好",
    "pinyin": "ni3 hao3", "audio_key": None, "translation_en": "Hello",
    "translation_vi": "Xin chào", "tokens": [],
}


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>/lines
# ---------------------------------------------------------------------------

def test_list_passage_lines_endpoint(client):
    with patch("routes.passage_line.passage_line_crud_routes.list_passage_lines", return_value=[LINE_DICT]) as mock_list:
        resp = client.get("/api/admin/passage/H1_1_1/lines")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"][0]["line_id"] == 1
    mock_list.assert_called_once_with("H1_1_1")


def test_list_passage_lines_endpoint_passage_not_found(client):
    with patch("routes.passage_line.passage_line_crud_routes.list_passage_lines",
               side_effect=PassageServiceError("Passage 'X' not found.", 404)):
        resp = client.get("/api/admin/passage/X/lines")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>/lines/<line_id>
# ---------------------------------------------------------------------------

def test_get_passage_line_endpoint_found(client):
    with patch("routes.passage_line.passage_line_crud_routes.get_passage_line", return_value=LINE_DICT):
        resp = client.get("/api/admin/passage/H1_1_1/lines/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["line_id"] == 1


def test_get_passage_line_endpoint_not_found(client):
    with patch("routes.passage_line.passage_line_crud_routes.get_passage_line",
               side_effect=PassageServiceError("Line 9 not found in passage 'H1_1_1'.", 404)):
        resp = client.get("/api/admin/passage/H1_1_1/lines/9")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/passage/<passage_id>/lines
# ---------------------------------------------------------------------------

def test_add_passage_line_endpoint_success(client):
    with patch("routes.passage_line.passage_line_crud_routes.add_passage_line", return_value=LINE_DICT) as mock_add:
        resp = client.post("/api/admin/passage/H1_1_1/lines", json={"line_id": 1, "content": "你好"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["line_id"] == 1
    mock_add.assert_called_once_with("H1_1_1", {"line_id": 1, "content": "你好"})


def test_add_passage_line_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/passage/H1_1_1/lines", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_add_passage_line_endpoint_duplicate(client):
    with patch("routes.passage_line.passage_line_crud_routes.add_passage_line",
               side_effect=PassageServiceError("Line 1 already exists in passage 'H1_1_1'. Use PUT to update it.", 409)):
        resp = client.post("/api/admin/passage/H1_1_1/lines", json={"line_id": 1})

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["success"] is False
    assert "already exists" in body["error"]


def test_add_passage_line_endpoint_missing_line_id(client):
    with patch("routes.passage_line.passage_line_crud_routes.add_passage_line",
               side_effect=PassageServiceError("Field 'line_id' is required.")):
        resp = client.post("/api/admin/passage/H1_1_1/lines", json={"content": "你好"})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "required" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/passage/<passage_id>/lines/<line_id>
# ---------------------------------------------------------------------------

def test_update_passage_line_endpoint_success(client):
    updated = {**LINE_DICT, "translation_en": "Hi"}
    with patch("routes.passage_line.passage_line_crud_routes.update_passage_line", return_value=updated):
        resp = client.put("/api/admin/passage/H1_1_1/lines/1", json={"translation_en": "Hi"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["translation_en"] == "Hi"


def test_update_passage_line_endpoint_not_found(client):
    with patch("routes.passage_line.passage_line_crud_routes.update_passage_line",
               side_effect=PassageServiceError("Line 9 not found in passage 'H1_1_1'.", 404)):
        resp = client.put("/api/admin/passage/H1_1_1/lines/9", json={"translation_en": "Hi"})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_update_passage_line_endpoint_rejects_non_json_body(client):
    resp = client.put("/api/admin/passage/H1_1_1/lines/1", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/passage/<passage_id>/lines/<line_id>
# ---------------------------------------------------------------------------

def test_delete_passage_line_endpoint_success(client):
    with patch("routes.passage_line.passage_line_crud_routes.delete_passage_line",
               return_value={"message": "Line 1 deleted from passage 'H1_1_1'."}):
        resp = client.delete("/api/admin/passage/H1_1_1/lines/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_passage_line_endpoint_not_found(client):
    with patch("routes.passage_line.passage_line_crud_routes.delete_passage_line",
               side_effect=PassageServiceError("Line 9 not found in passage 'H1_1_1'.", 404)):
        resp = client.delete("/api/admin/passage/H1_1_1/lines/9")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
