import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.passage_vocab.passage_vocab_crud_routes import passage_vocab_crud_bp
from entity.passage_vocabulary.service import PassageVocabularyServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(passage_vocab_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


VOCAB_ITEM = {"cn": "你好", "pinyin": "ni3 hao3", "meaning_en": "Hello", "meaning_vn": "Xin chào",
              "audio_key": None, "hsk_level": "HSK1", "source": None}


# ---------------------------------------------------------------------------
# GET /api/admin/passage/<passage_id>/vocabulary
# ---------------------------------------------------------------------------

def test_list_passage_vocab_endpoint(client):
    with patch("routes.passage_vocab.passage_vocab_crud_routes.list_passage_vocab", return_value={
        "passage_id": "H1_1_1", "items": [VOCAB_ITEM], "total": 1
    }) as mock_list:
        resp = client.get("/api/admin/passage/H1_1_1/vocabulary")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["items"][0]["cn"] == "你好"
    mock_list.assert_called_once_with("H1_1_1")


def test_list_passage_vocab_endpoint_passage_not_found(client):
    with patch("routes.passage_vocab.passage_vocab_crud_routes.list_passage_vocab",
               side_effect=PassageVocabularyServiceError("Passage 'X' not found.", 404)):
        resp = client.get("/api/admin/passage/X/vocabulary")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/passage/<passage_id>/vocabulary
# ---------------------------------------------------------------------------

def test_add_passage_vocab_endpoint_success(client):
    with patch("routes.passage_vocab.passage_vocab_crud_routes.add_passage_vocab", return_value={
        "message": "'你好' linked to passage 'H1_1_1'.", "passage_id": "H1_1_1", "cn": "你好"
    }) as mock_add:
        resp = client.post("/api/admin/passage/H1_1_1/vocabulary", json={"cn": "你好"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["cn"] == "你好"
    mock_add.assert_called_once_with("H1_1_1", "你好")


def test_add_passage_vocab_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/passage/H1_1_1/vocabulary", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_add_passage_vocab_endpoint_duplicate_link(client):
    with patch("routes.passage_vocab.passage_vocab_crud_routes.add_passage_vocab",
               side_effect=PassageVocabularyServiceError("'你好' is already linked to passage 'H1_1_1'.", 409)):
        resp = client.post("/api/admin/passage/H1_1_1/vocabulary", json={"cn": "你好"})

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["success"] is False
    assert "already linked" in body["error"]


# ---------------------------------------------------------------------------
# DELETE /api/admin/passage/<passage_id>/vocabulary/<cn>
# ---------------------------------------------------------------------------

def test_remove_passage_vocab_endpoint_success(client):
    with patch("routes.passage_vocab.passage_vocab_crud_routes.remove_passage_vocab",
               return_value={"message": "'你好' unlinked from passage 'H1_1_1'."}):
        resp = client.delete("/api/admin/passage/H1_1_1/vocabulary/你好")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "unlinked" in body["data"]["message"]


def test_remove_passage_vocab_endpoint_not_found(client):
    with patch("routes.passage_vocab.passage_vocab_crud_routes.remove_passage_vocab",
               side_effect=PassageVocabularyServiceError("'你好' is not linked to passage 'H1_1_1'.", 404)):
        resp = client.delete("/api/admin/passage/H1_1_1/vocabulary/你好")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
