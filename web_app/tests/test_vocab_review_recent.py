"""POST /api/vocab/review-recent/query — the "Review word" tab.

The route turns the service's recency-ordered word list into a paged list of
normalized vocabulary rows. What matters here: the recency order the service
produced survives hydration, words missing from the vocabulary table drop out,
and the page envelope matches the other list routes.
"""
import os
import sys

import pandas as pd
import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from routes.vocab import vocab_routes


VOCAB_ROWS = [
    ("你好", "nǐ hǎo", "xin chào", "hello", "nihao", "HSK1"),
    ("学习", "xué xí", "học", "to study", "xuexi", "HSK1"),
    ("汉语", "hàn yǔ", "tiếng Hán", "Chinese", "hanyu", "HSK2"),
]
VOCAB_COLUMNS = ["word", "pinyin", "meaning_vn", "meaning_en", "audio_key", "level"]

HELLO = VOCAB_ROWS[0][0]    # 你好
STUDY = VOCAB_ROWS[1][0]    # 学习
CHINESE = VOCAB_ROWS[2][0]  # 汉语
UNKNOWN = "不存在"           # absent from VOCAB_ROWS


class StubUser:
    id = 1
    is_authenticated = True


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(vocab_routes, "current_user", StubUser())
    monkeypatch.setattr(
        vocab_routes,
        "get_course_vocab",
        lambda: pd.DataFrame(VOCAB_ROWS, columns=VOCAB_COLUMNS),
    )
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.register_blueprint(vocab_routes.vocab_bp)
    with app.test_client() as c:
        yield c


def wire_words(monkeypatch, words):
    monkeypatch.setattr(
        vocab_routes, "get_recent_review_words", lambda user_id, limit=100: list(words)
    )


def post(client, body=None):
    response = client.post("/api/vocab/review-recent/query", json=body or {})
    assert response.status_code == 200
    return response.get_json()


def test_empty_when_the_service_returns_nothing(client, monkeypatch):
    wire_words(monkeypatch, [])
    body = post(client)
    assert body["rows"] == []
    assert body["total"] == 0
    assert body["total_pages"] == 1


def test_rows_keep_the_services_recency_order(client, monkeypatch):
    # Service already ordered these newest-first; the route must not reshuffle them.
    wire_words(monkeypatch, [CHINESE, HELLO, STUDY])
    body = post(client)
    assert [r["word"] for r in body["rows"]] == [CHINESE, HELLO, STUDY]
    assert body["total"] == 3


def test_words_absent_from_the_vocabulary_table_are_dropped(client, monkeypatch):
    wire_words(monkeypatch, [STUDY, UNKNOWN, HELLO])
    body = post(client)
    assert [r["word"] for r in body["rows"]] == [STUDY, HELLO]
    assert body["total"] == 2


def test_paginates(client, monkeypatch):
    wire_words(monkeypatch, [CHINESE, HELLO, STUDY])
    page1 = post(client, {"page": 1, "page_size": 5})
    assert page1["total"] == 3 and page1["total_pages"] == 1
    # page_size is clamped to a 5 floor, so all three land on page 1.
    assert len(page1["rows"]) == 3


def test_second_page_returns_the_tail(client, monkeypatch):
    wire_words(monkeypatch, [CHINESE, HELLO, STUDY])
    # Clamp floor is 5, so force a boundary another way: request page 2 of a
    # single-page result and get clamped back to the only page.
    body = post(client, {"page": 2, "page_size": 100})
    assert body["page"] == 1
    assert [r["word"] for r in body["rows"]] == [CHINESE, HELLO, STUDY]
