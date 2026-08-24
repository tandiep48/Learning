import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.question_crud_routes import question_crud_bp
from entity.question.service import QuestionServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(question_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


QUESTION_DICT = {
    "id": 1, "category": "practice", "level": 1, "lesson": 1, "no": 1, "type": 1,
    "progress": "vocab", "skill": None, "content": None, "question": "你好?",
    "answer": "A", "audio_key": None, "image": None, "options": None, "unit_id": "",
}


# ---------------------------------------------------------------------------
# GET /api/admin/question
# ---------------------------------------------------------------------------

def test_list_questions_endpoint(client):
    with patch("routes.question_crud_routes.list_questions", return_value={
        "items": [QUESTION_DICT], "page": 1, "page_size": 20, "total": 1, "total_pages": 1
    }) as mock_list:
        resp = client.get(
            "/api/admin/question?page=1&page_size=20&category=practice&level=1&lesson=1&skill=reading&search=hi"
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["items"][0]["category"] == "practice"
    mock_list.assert_called_once_with(
        page=1, page_size=20, category="practice", level="1", lesson="1",
        skill="reading", search="hi",
    )


def test_list_questions_endpoint_rejects_non_integer_paging(client):
    resp = client.get("/api/admin/question?page=abc")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_list_questions_endpoint_propagates_service_validation_error(client):
    with patch("routes.question_crud_routes.list_questions",
               side_effect=QuestionServiceError("Field 'category' must be one of: exam, practice.")):
        resp = client.get("/api/admin/question?category=bogus")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "category" in body["error"]


# ---------------------------------------------------------------------------
# GET /api/admin/question/<question_id>
# ---------------------------------------------------------------------------

def test_get_question_endpoint_found(client):
    with patch("routes.question_crud_routes.get_question", return_value=QUESTION_DICT):
        resp = client.get("/api/admin/question/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == 1


def test_get_question_endpoint_not_found(client):
    with patch("routes.question_crud_routes.get_question",
               side_effect=QuestionServiceError("Question with id=999 not found.", 404)):
        resp = client.get("/api/admin/question/999")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/question
# ---------------------------------------------------------------------------

def test_create_question_endpoint_success(client):
    with patch("routes.question_crud_routes.create_question", return_value=QUESTION_DICT):
        resp = client.post("/api/admin/question", json={
            "category": "practice", "level": 1, "lesson": 1, "no": 1, "type": 1, "progress": "vocab",
        })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["category"] == "practice"


def test_create_question_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/question", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_create_question_endpoint_conflict(client):
    with patch("routes.question_crud_routes.create_question",
               side_effect=QuestionServiceError(
                   "A practice question already exists for level 1, lesson 1, no 1.", 409)):
        resp = client.post("/api/admin/question", json={
            "category": "practice", "level": 1, "lesson": 1, "no": 1, "type": 1, "progress": "vocab",
        })

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["success"] is False
    assert "already exists" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/question/<question_id>
# ---------------------------------------------------------------------------

def test_update_question_endpoint_success(client):
    updated = {**QUESTION_DICT, "answer": "B"}
    with patch("routes.question_crud_routes.update_question", return_value=updated):
        resp = client.put("/api/admin/question/1", json={"answer": "B"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["answer"] == "B"


def test_update_question_endpoint_not_found(client):
    with patch("routes.question_crud_routes.update_question",
               side_effect=QuestionServiceError("Question with id=999 not found.", 404)):
        resp = client.put("/api/admin/question/999", json={"answer": "B"})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_update_question_endpoint_rejects_non_json_body(client):
    resp = client.put("/api/admin/question/1", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/question/<question_id>
# ---------------------------------------------------------------------------

def test_delete_question_endpoint_success(client):
    with patch("routes.question_crud_routes.delete_question",
               return_value={"message": "Question id=1 deleted successfully."}):
        resp = client.delete("/api/admin/question/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_question_endpoint_not_found(client):
    with patch("routes.question_crud_routes.delete_question",
               side_effect=QuestionServiceError("Question with id=999 not found.", 404)):
        resp = client.delete("/api/admin/question/999")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
