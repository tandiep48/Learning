"""
POST .../query twins of the learner list/search reads.

Each endpoint validates a JSON body (422 on bad input) and returns the same raw
shape as its existing GET. The data/service functions are monkeypatched, so the
tests exercise validation + the shared helper wiring, not the DB.
"""
import os
import sys

import pandas as pd
import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.vocab import vocab_routes
from routes.user import user_routes
from routes.practice import practice_routes


class StubUser:
    id = 1
    is_authenticated = True


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(vocab_routes, "current_user", StubUser())
    monkeypatch.setattr(user_routes, "current_user", StubUser())
    monkeypatch.setattr(practice_routes, "current_user", StubUser())
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.register_blueprint(vocab_routes.vocab_bp)
    app.register_blueprint(user_routes.user_bp)
    app.register_blueprint(practice_routes.practice_bp)
    with app.test_client() as c:
        yield c


EMPTY_DF = pd.DataFrame(columns=["word", "pinyin", "meaning_vn", "meaning_en", "audio_key", "level"])


# ── /api/vocab/search/query ────────────────────────────────────────────────
def test_search_query_valid(client, monkeypatch):
    monkeypatch.setattr(vocab_routes, "get_full_lesson_records", lambda: EMPTY_DF)
    resp = client.post("/api/vocab/search/query", json={"q": "hello", "page": 1, "page_size": 20})
    assert resp.status_code == 200
    assert resp.get_json()["rows"] == []


def test_search_query_rejects_bad_page(client):
    resp = client.post("/api/vocab/search/query", json={"page": 0})
    assert resp.status_code == 422
    assert resp.get_json()["success"] is False


# ── /api/vocab/table/query ─────────────────────────────────────────────────
def test_table_query_free_empty(client):
    resp = client.post("/api/vocab/table/query", json={"mode": "free"})
    assert resp.status_code == 200
    assert resp.get_json()["rows"] == []


def test_table_query_rejects_bad_mode(client):
    resp = client.post("/api/vocab/table/query", json={"mode": "bogus"})
    assert resp.status_code == 422


def test_table_query_accepts_large_page_size(client):
    # The vocab-select UI offers sizes up to 1000; the body must not reject them.
    resp = client.post("/api/vocab/table/query", json={"mode": "free", "page_size": 1000})
    assert resp.status_code == 200


# ── /api/vocab/review/query ────────────────────────────────────────────────
def test_review_query_empty(client, monkeypatch):
    monkeypatch.setattr(vocab_routes, "get_review_words_flat", lambda uid: [])
    resp = client.post("/api/vocab/review/query", json={})
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 0


def test_review_query_rejects_bad_page(client):
    resp = client.post("/api/vocab/review/query", json={"page": 0})
    assert resp.status_code == 422


# ── /api/user/learned-vocab/query ──────────────────────────────────────────
def test_learned_vocab_query(client, monkeypatch):
    monkeypatch.setattr(
        user_routes, "get_mastered_words_page",
        lambda uid, page, ps: {"rows": [], "page": page, "page_size": ps, "total": 0, "total_pages": 1},
    )
    resp = client.post("/api/user/learned-vocab/query", json={"page": 2, "page_size": 24})
    assert resp.status_code == 200
    assert resp.get_json()["page"] == 2


def test_learned_vocab_query_rejects_bad_size(client):
    resp = client.post("/api/user/learned-vocab/query", json={"page_size": 0})
    assert resp.status_code == 422


# ── /api/practice/history/query ────────────────────────────────────────────
def test_practice_history_query(client, monkeypatch):
    monkeypatch.setattr(practice_routes, "get_practice_history_sessions", lambda uid, **k: ([], False))
    resp = client.post(
        "/api/practice/history/query",
        json={"level": "all", "category": "practice", "sort": "recent", "page": 1},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["sessions"] == [] and body["has_more"] is False


def test_practice_history_query_normalizes_loose_filters(client, monkeypatch):
    captured = {}

    def fake(uid, **kwargs):
        captured.update(kwargs)
        return ([], False)

    monkeypatch.setattr(practice_routes, "get_practice_history_sessions", fake)
    resp = client.post(
        "/api/practice/history/query",
        json={"level": "9x", "category": "nope", "sort": "weird"},
    )
    assert resp.status_code == 200
    assert captured["category"] is None
    assert captured["sort"] == "recent"
    assert captured["hsk_level"] is None


def test_practice_history_query_rejects_bad_page(client):
    resp = client.post("/api/practice/history/query", json={"page": 0})
    assert resp.status_code == 422
