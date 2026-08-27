import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.grammar_context.grammar_context_crud_routes import grammar_context_crud_bp
from entity.grammar_context.service import GrammarContextServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(grammar_context_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


CONTEXT_DICT = {
    "id": 1, "grammar_id": "H1-2-1", "content_json": {"note": "example"},
}


# ---------------------------------------------------------------------------
# GET /api/admin/grammar_context
# ---------------------------------------------------------------------------

def test_list_grammar_contexts_endpoint(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.list_grammar_contexts", return_value={
        "items": [CONTEXT_DICT], "page": 1, "page_size": 20, "total": 1, "total_pages": 1
    }) as mock_list:
        resp = client.get("/api/admin/grammar_context?page=1&page_size=20&grammar_id=H1-2-1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["items"][0]["grammar_id"] == "H1-2-1"
    mock_list.assert_called_once_with(page=1, page_size=20, grammar_id="H1-2-1")


def test_list_grammar_contexts_endpoint_rejects_non_integer_paging(client):
    resp = client.get("/api/admin/grammar_context?page=abc")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


# ---------------------------------------------------------------------------
# GET /api/admin/grammar_context/<context_id>
# ---------------------------------------------------------------------------

def test_get_grammar_context_endpoint_found(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.get_grammar_context", return_value=CONTEXT_DICT):
        resp = client.get("/api/admin/grammar_context/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == 1


def test_get_grammar_context_endpoint_not_found(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.get_grammar_context",
               side_effect=GrammarContextServiceError("Grammar context with id=999 not found.", 404)):
        resp = client.get("/api/admin/grammar_context/999")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/grammar_context
# ---------------------------------------------------------------------------

def test_create_grammar_context_endpoint_success(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.create_grammar_context", return_value=CONTEXT_DICT):
        resp = client.post("/api/admin/grammar_context", json={"grammar_id": "H1-2-1"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["grammar_id"] == "H1-2-1"


def test_create_grammar_context_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/grammar_context", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_create_grammar_context_endpoint_service_error(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.create_grammar_context",
               side_effect=GrammarContextServiceError("Field 'grammar_id' is required.")):
        resp = client.post("/api/admin/grammar_context", json={"content_json": {}})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "required" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/grammar_context/<context_id>
# ---------------------------------------------------------------------------

def test_update_grammar_context_endpoint_success(client):
    updated = {**CONTEXT_DICT, "content_json": {"note": "updated"}}
    with patch("routes.grammar_context.grammar_context_crud_routes.update_grammar_context", return_value=updated):
        resp = client.put("/api/admin/grammar_context/1", json={"content_json": {"note": "updated"}})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["content_json"] == {"note": "updated"}


def test_update_grammar_context_endpoint_not_found(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.update_grammar_context",
               side_effect=GrammarContextServiceError("Grammar context with id=999 not found.", 404)):
        resp = client.put("/api/admin/grammar_context/999", json={"content_json": {}})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_update_grammar_context_endpoint_rejects_non_json_body(client):
    resp = client.put("/api/admin/grammar_context/1", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/grammar_context/<context_id>
# ---------------------------------------------------------------------------

def test_delete_grammar_context_endpoint_success(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.delete_grammar_context",
               return_value={"message": "Grammar context id=1 deleted successfully."}):
        resp = client.delete("/api/admin/grammar_context/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_grammar_context_endpoint_not_found(client):
    with patch("routes.grammar_context.grammar_context_crud_routes.delete_grammar_context",
               side_effect=GrammarContextServiceError("Grammar context with id=999 not found.", 404)):
        resp = client.delete("/api/admin/grammar_context/999")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
