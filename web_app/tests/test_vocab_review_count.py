"""GET /api/vocab/review/count.

The property that matters is agreement: the count must equal the `total` that
GET /api/vocab/review reports for the same user, while never calling
get_course_vocab() — the uncached full-table load the count route exists to avoid.
"""
import os
import sys

import pandas as pd
import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from routes.vocab import vocab_routes


# A stand-in vocabulary table, in the shape get_course_vocab() returns.
VOCAB_ROWS = [
    ("你好", "nǐ hǎo", "xin chào", "hello", "nihao", "HSK1"),
    ("学习", "xué xí", "học", "to study", "xuexi", "HSK1"),
    ("汉语", "hàn yǔ", "tiếng Hán", "Chinese", "hanyu", "HSK2"),
]
VOCAB_COLUMNS = ["word", "pinyin", "meaning_vn", "meaning_en", "audio_key", "level"]
KNOWN = {row[0] for row in VOCAB_ROWS}

STUDY = VOCAB_ROWS[1][0]      # 学习
CHINESE = VOCAB_ROWS[2][0]    # 汉语
HELLO = VOCAB_ROWS[0][0]      # 你好
UNKNOWN = "不存在"  # 不存在 — deliberately absent from VOCAB_ROWS


class StubUser:
    id = 1
    is_authenticated = True


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(vocab_routes, "current_user", StubUser())
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.register_blueprint(vocab_routes.vocab_bp)
    with app.test_client() as c:
        yield c


def wire(monkeypatch, review_words, *, forbid_course_vocab=False):
    """Point both the count route and the list route at the same fake data."""
    monkeypatch.setattr(
        vocab_routes, "get_review_words_flat", lambda user_id: list(review_words)
    )
    monkeypatch.setattr(
        vocab_routes,
        "get_existing_vocab_words",
        lambda words: {w for w in words if w in KNOWN},
    )

    if forbid_course_vocab:
        def fail_load():
            raise AssertionError(
                "get_course_vocab() was called — the count route must not load "
                "the whole vocabulary table"
            )
        monkeypatch.setattr(vocab_routes, "get_course_vocab", fail_load)
    else:
        monkeypatch.setattr(
            vocab_routes,
            "get_course_vocab",
            lambda: pd.DataFrame(VOCAB_ROWS, columns=VOCAB_COLUMNS),
        )


def count_of(client):
    response = client.get("/api/vocab/review/count")
    assert response.status_code == 200
    return response.get_json()["total"]


def list_total_of(client):
    response = client.get("/api/vocab/review")
    assert response.status_code == 200
    return response.get_json()["total"]


def a_number_word():
    """A word present only in the static number rows, not in VOCAB_ROWS."""
    for row in vocab_routes.number_vocab_rows(include_all=True):
        word = vocab_routes.normalize_vocab_row(row)["word"]
        if word not in KNOWN:
            return word
    raise AssertionError("no number word outside the fake vocabulary table")


def test_empty_review_list_counts_zero(client, monkeypatch):
    wire(monkeypatch, [], forbid_course_vocab=True)

    assert count_of(client) == 0


def test_counts_only_words_present_in_the_vocabulary_table(client, monkeypatch):
    wire(monkeypatch, [STUDY, CHINESE, UNKNOWN], forbid_course_vocab=True)

    assert count_of(client) == 2


def test_duplicate_and_padded_words_count_once(client, monkeypatch):
    wire(monkeypatch, [STUDY, STUDY, f" {STUDY} "], forbid_course_vocab=True)

    assert count_of(client) == 1


def test_number_words_are_counted(client, monkeypatch):
    wire(monkeypatch, [STUDY, a_number_word()], forbid_course_vocab=True)

    assert count_of(client) == 2


def test_a_word_in_both_sources_is_not_double_counted(client, monkeypatch):
    number_word = a_number_word()
    monkeypatch.setattr(
        vocab_routes, "get_review_words_flat", lambda user_id: [STUDY, number_word]
    )
    # This number word also exists as a vocabulary row, as it does in the real database.
    monkeypatch.setattr(
        vocab_routes,
        "get_existing_vocab_words",
        lambda words: {w for w in words if w in {STUDY, number_word}},
    )

    assert count_of(client) == 2


def test_count_never_loads_the_whole_vocabulary_table(client, monkeypatch):
    wire(monkeypatch, [STUDY, CHINESE], forbid_course_vocab=True)

    # The fail_load() stub would have raised had the expensive path been taken.
    assert count_of(client) == 2


@pytest.mark.parametrize(
    "review_words",
    [
        [],
        [STUDY],
        [STUDY, CHINESE, HELLO],
        [STUDY, UNKNOWN],
        [STUDY, STUDY],
    ],
)
def test_count_agrees_with_the_list_endpoint_total(client, monkeypatch, review_words):
    """The contract: /review/count == /review's `total`, for the same user."""
    wire(monkeypatch, review_words)

    assert count_of(client) == list_total_of(client)
