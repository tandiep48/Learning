import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.grammar_rule.grammar_rule_crud_routes import grammar_rule_crud_bp
from entity.grammar_rule.service import GrammarRuleServiceError


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(grammar_rule_crud_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


RULE_DICT = {
    "id": 1, "grammar_id": "H1-2-1", "type": 1, "passage_number": 1,
    "vietnamese_content": "Noi dung", "english_content": "Content",
}


# ---------------------------------------------------------------------------
# GET /api/admin/grammar_rule
# ---------------------------------------------------------------------------

def test_list_grammar_rules_endpoint(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.list_grammar_rules", return_value={
        "items": [RULE_DICT], "page": 1, "page_size": 20, "total": 1, "total_pages": 1
    }) as mock_list:
        resp = client.get("/api/admin/grammar_rule?page=1&page_size=20&grammar_id=H1-2-1&type=1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["items"][0]["grammar_id"] == "H1-2-1"
    mock_list.assert_called_once_with(page=1, page_size=20, grammar_id="H1-2-1", type_=1)


def test_list_grammar_rules_endpoint_rejects_non_integer_paging(client):
    resp = client.get("/api/admin/grammar_rule?page=abc")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_list_grammar_rules_endpoint_rejects_non_integer_type(client):
    resp = client.get("/api/admin/grammar_rule?type=abc")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


# ---------------------------------------------------------------------------
# GET /api/admin/grammar_rule/<rule_id>
# ---------------------------------------------------------------------------

def test_get_grammar_rule_endpoint_found(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.get_grammar_rule", return_value=RULE_DICT):
        resp = client.get("/api/admin/grammar_rule/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == 1


def test_get_grammar_rule_endpoint_not_found(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.get_grammar_rule",
               side_effect=GrammarRuleServiceError("Grammar rule with id=999 not found.", 404)):
        resp = client.get("/api/admin/grammar_rule/999")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/admin/grammar_rule
# ---------------------------------------------------------------------------

def test_create_grammar_rule_endpoint_success(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.create_grammar_rule", return_value=RULE_DICT):
        resp = client.post("/api/admin/grammar_rule", json={"grammar_id": "H1-2-1"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["grammar_id"] == "H1-2-1"


def test_create_grammar_rule_endpoint_rejects_non_json_body(client):
    resp = client.post("/api/admin/grammar_rule", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False


def test_create_grammar_rule_endpoint_service_error(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.create_grammar_rule",
               side_effect=GrammarRuleServiceError("Field 'grammar_id' is required.")):
        resp = client.post("/api/admin/grammar_rule", json={"type": 1})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "required" in body["error"]


# ---------------------------------------------------------------------------
# PUT /api/admin/grammar_rule/<rule_id>
# ---------------------------------------------------------------------------

def test_update_grammar_rule_endpoint_success(client):
    updated = {**RULE_DICT, "english_content": "Updated"}
    with patch("routes.grammar_rule.grammar_rule_crud_routes.update_grammar_rule", return_value=updated):
        resp = client.put("/api/admin/grammar_rule/1", json={"english_content": "Updated"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["english_content"] == "Updated"


def test_update_grammar_rule_endpoint_not_found(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.update_grammar_rule",
               side_effect=GrammarRuleServiceError("Grammar rule with id=999 not found.", 404)):
        resp = client.put("/api/admin/grammar_rule/999", json={"english_content": "Updated"})

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_update_grammar_rule_endpoint_rejects_non_json_body(client):
    resp = client.put("/api/admin/grammar_rule/1", data="not json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/admin/grammar_rule/<rule_id>
# ---------------------------------------------------------------------------

def test_delete_grammar_rule_endpoint_success(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.delete_grammar_rule",
               return_value={"message": "Grammar rule id=1 deleted successfully."}):
        resp = client.delete("/api/admin/grammar_rule/1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "deleted" in body["data"]["message"]


def test_delete_grammar_rule_endpoint_not_found(client):
    with patch("routes.grammar_rule.grammar_rule_crud_routes.delete_grammar_rule",
               side_effect=GrammarRuleServiceError("Grammar rule with id=999 not found.", 404)):
        resp = client.delete("/api/admin/grammar_rule/999")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
