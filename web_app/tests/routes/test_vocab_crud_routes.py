import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.vocab.vocab_crud_routes import vocab_crud_bp
from entity.vocabulary.service import VocabServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(vocab_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


VOCAB_DICT = {
    "id": 1, "cn": "你好", "pinyin": "ni3 hao3", "meaning_en": "Hello",
    "meaning_vn": "Xin chào", "audio_key": None, "hsk_level": "HSK1", "source": None,
}


# ---------------------------------------------------------------------------
# POST /api/admin/vocab/query
# ---------------------------------------------------------------------------

def test_query_vocab_endpoint(client):
    with patch("routes.vocab.vocab_crud_routes.list_vocab", return_value={
        "items": [VOCAB_DICT], "page": 1, "page_size": 20, "total": 1, "total_pages": 1
    }) as mock_list:
        resp = client.post(
            "/api/admin/vocab/query",
            json={"page": 1, "page_size": 20, "hsk_level": "HSK1", "search": "hao"},
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["items"][0]["cn"] == "你好"
    mock_list.assert_called_once_with(page=1, page_size=20, hsk_level="HSK1", search="hao")


def test_query_vocab_endpoint_applies_defaults_on_empty_body(client):
    with patch("routes.vocab.vocab_crud_routes.list_vocab", return_value={
        "items": [], "page": 1, "page_size": 20, "total": 0, "total_pages": 1
    }) as mock_list:
        resp = client.post("/api/admin/vocab/query", json={})

    assert resp.status_code == 200
    mock_list.assert_called_once_with(page=1, page_size=20, hsk_level=None, search=None)


def test_query_vocab_endpoint_rejects_out_of_range_page_size(client):
    resp = client.post("/api/admin/vocab/query", json={"page_size": 500})

    assert resp.status_code == 422
    body = resp.get_json()
    assert body["success"] is False
    assert body["details"][0]["field"] == "page_size"


def test_query_vocab_endpoint_rejects_unknown_hsk_level(client):
    resp = client.post("/api/admin/vocab/query", json={"hsk_level": "HSK9"})

    assert resp.status_code == 422
    assert resp.get_json()["success"] is False


def test_query_vocab_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/vocab/query", data="not json", content_type="text/plain")

    assert resp.status_code == 422
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# GET /api/admin/vocab/<vocab_id>
# ---------------------------------------------------------------------------

def test_get_vocab_endpoint_found(client):
    with patch("routes.vocab.vocab_crud_routes.get_vocab", return_value=VOCAB_DICT):
        resp = client.get("/api/admin/vocab/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == 1


def test_get_vocab_endpoint_not_found(client):
    with patch("routes.vocab.vocab_crud_routes.get_vocab",
               side_effect=VocabServiceError("Vocabulary with id=999 not found.", 404)):
        resp = client.get("/api/admin/vocab/999")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/vocab
# ---------------------------------------------------------------------------

def test_create_vocab_endpoint_success(client):
    with patch("routes.vocab.vocab_crud_routes.create_vocab", return_value=VOCAB_DICT):
        resp = client.post("/api/admin/vocab", json={"cn": "你好"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["cn"] == "你好"


def test_create_vocab_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/vocab", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_create_vocab_endpoint_service_error(client):
    with patch("routes.vocab.vocab_crud_routes.create_vocab",
               side_effect=VocabServiceError("Vocabulary '你好' already exists. Use PUT to update it.")):
        resp = client.post("/api/admin/vocab", json={"cn": "你好"})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "already exists" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/vocab/<vocab_id>
# ---------------------------------------------------------------------------

def test_update_vocab_endpoint_success(client):
    updated = {**VOCAB_DICT, "meaning_en": "Hi"}
    with patch("routes.vocab.vocab_crud_routes.update_vocab", return_value=updated):
        resp = client.put("/api/admin/vocab/1", json={"meaning_en": "Hi"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["meaning_en"] == "Hi"


def test_update_vocab_endpoint_not_found(client):
    with patch("routes.vocab.vocab_crud_routes.update_vocab",
               side_effect=VocabServiceError("Vocabulary with id=999 not found.", 404)):
        resp = client.put("/api/admin/vocab/999", json={"meaning_en": "Hi"})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_update_vocab_endpoint_rejects_non_json_body(client):
    resp = client.put("/api/admin/vocab/1", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/vocab/<vocab_id>
# ---------------------------------------------------------------------------

def test_delete_vocab_endpoint_success(client):
    with patch("routes.vocab.vocab_crud_routes.delete_vocab",
               return_value={"message": "Vocabulary id=1 deleted successfully."}):
        resp = client.delete("/api/admin/vocab/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_vocab_endpoint_not_found(client):
    with patch("routes.vocab.vocab_crud_routes.delete_vocab",
               side_effect=VocabServiceError("Vocabulary with id=999 not found.", 404)):
        resp = client.delete("/api/admin/vocab/999")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
