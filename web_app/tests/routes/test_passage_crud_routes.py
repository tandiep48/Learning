import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.passage_crud_routes import passage_crud_bp
from entity.passage.service import PassageServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(passage_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


PASSAGE_DICT = {"passage_id": "H1_1_1", "hsk_level": "HSK1", "book_code": None}
PASSAGE_WITH_LINES = {**PASSAGE_DICT, "lines": [
    {"id": 1, "passage_id": "H1_1_1", "line_id": 1, "speaker": "A", "content": "你好",
     "pinyin": "ni3 hao3", "audio_key": None, "translation_en": "Hello",
     "translation_vi": "Xin chào", "tokens": []},
]}


# ---------------------------------------------------------------------------
# GET /api/admin/passage
# ---------------------------------------------------------------------------

def test_list_passages_endpoint(client):
    with patch("routes.passage_crud_routes.list_passages", return_value={
        "items": [PASSAGE_DICT], "page": 1, "page_size": 20, "total": 1, "total_pages": 1
    }) as mock_list:
        resp = client.get("/api/admin/passage?page=1&page_size=20&hsk_level=HSK1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["items"][0]["passage_id"] == "H1_1_1"
    mock_list.assert_called_once_with(page=1, page_size=20, hsk_level="HSK1")


def test_list_passages_endpoint_rejects_non_integer_paging(client):
    resp = client.get("/api/admin/passage?page=abc")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>
# ---------------------------------------------------------------------------

def test_get_passage_endpoint_found(client):
    with patch("routes.passage_crud_routes.get_passage", return_value=PASSAGE_WITH_LINES):
        resp = client.get("/api/admin/passage/H1_1_1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["passage_id"] == "H1_1_1"
    assert len(body["data"]["lines"]) == 1


def test_get_passage_endpoint_not_found(client):
    with patch("routes.passage_crud_routes.get_passage",
               side_effect=PassageServiceError("Passage 'X' not found.", 404)):
        resp = client.get("/api/admin/passage/X")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/passage
# ---------------------------------------------------------------------------

def test_create_passage_endpoint_success(client):
    with patch("routes.passage_crud_routes.create_passage", return_value=PASSAGE_WITH_LINES):
        resp = client.post("/api/admin/passage", json={"passage_id": "H1_1_1"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["passage_id"] == "H1_1_1"


def test_create_passage_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/passage", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_create_passage_endpoint_service_error(client):
    with patch("routes.passage_crud_routes.create_passage",
               side_effect=PassageServiceError("Passage 'H1_1_1' already exists. Use PUT to update it.")):
        resp = client.post("/api/admin/passage", json={"passage_id": "H1_1_1"})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "already exists" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/passage/<passage_id>
# ---------------------------------------------------------------------------

def test_update_passage_endpoint_success(client):
    updated = {**PASSAGE_DICT, "hsk_level": "HSK2"}
    with patch("routes.passage_crud_routes.update_passage", return_value=updated):
        resp = client.put("/api/admin/passage/H1_1_1", json={"hsk_level": "HSK2"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["hsk_level"] == "HSK2"


def test_update_passage_endpoint_not_found(client):
    with patch("routes.passage_crud_routes.update_passage",
               side_effect=PassageServiceError("Passage 'X' not found.", 404)):
        resp = client.put("/api/admin/passage/X", json={"hsk_level": "HSK2"})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_update_passage_endpoint_rejects_non_json_body(client):
    resp = client.put("/api/admin/passage/H1_1_1", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/passage/<passage_id>
# ---------------------------------------------------------------------------

def test_delete_passage_endpoint_success(client):
    with patch("routes.passage_crud_routes.delete_passage",
               return_value={"message": "Passage 'H1_1_1' and all its lines deleted successfully."}):
        resp = client.delete("/api/admin/passage/H1_1_1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_passage_endpoint_not_found(client):
    with patch("routes.passage_crud_routes.delete_passage",
               side_effect=PassageServiceError("Passage 'X' not found.", 404)):
        resp = client.delete("/api/admin/passage/X")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
