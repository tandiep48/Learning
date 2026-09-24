import os
import sys

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from routes import vocab_routes

# login_required wraps the view with functools.wraps, so the plain view is here.
lookup_batch = vocab_routes.lookup_batch.__wrapped__

app = Flask(__name__)


def call_lookup(words):
    query = ",".join(words)
    with app.test_request_context(f"/api/vocab/lookup-batch?words={query}"):
        return lookup_batch().get_json()


def fake_vocabulary(known):
    """Return a get_vocabulary_by_words stub plus the list of asked batches."""
    asked = []

    def _get(words):
        asked.append(list(words))
        return [
            {"word": w, "pinyin": f"py-{w}", "meaning_vn": f"vn-{w}",
             "meaning_en": f"en-{w}", "audio_key": f"audio-{w}"}
            for w in words if w in known
        ]

    return _get, asked


@pytest.fixture(autouse=True)
def clear_cache():
    vocab_routes._word_cache.clear()
    yield
    vocab_routes._word_cache.clear()


def test_lookup_batch_answers_every_word_of_a_long_lesson(monkeypatch):
    words = [f"词{i}" for i in range(300)]
    stub, asked = fake_vocabulary(set(words))
    monkeypatch.setattr(vocab_routes, "get_vocabulary_by_words", stub)

    data = call_lookup(words)

    # The old 80-word cap silently dropped the tail of a book lesson.
    assert len(data) == 300
    assert data["词299"]["pinyin"] == "py-词299"
    # Asked in chunks, and every word reached the database exactly once.
    assert sum(len(batch) for batch in asked) == 300
    assert max(len(batch) for batch in asked) <= vocab_routes.LOOKUP_CHUNK


def test_lookup_batch_caps_absurd_requests(monkeypatch):
    words = [f"词{i}" for i in range(vocab_routes.MAX_LOOKUP_WORDS + 50)]
    stub, _ = fake_vocabulary(set(words))
    monkeypatch.setattr(vocab_routes, "get_vocabulary_by_words", stub)

    data = call_lookup(words)

    assert len(data) == vocab_routes.MAX_LOOKUP_WORDS


def test_lookup_batch_does_not_remember_a_missing_word(monkeypatch):
    stub, _ = fake_vocabulary(set())
    monkeypatch.setattr(vocab_routes, "get_vocabulary_by_words", stub)
    assert call_lookup(["按钮"]) == {}

    # The dictionary import adds the word; the reader must see it without a restart.
    stub, _ = fake_vocabulary({"按钮"})
    monkeypatch.setattr(vocab_routes, "get_vocabulary_by_words", stub)
    assert call_lookup(["按钮"])["按钮"]["meaning_en"] == "en-按钮"


def test_lookup_batch_serves_a_hit_from_cache_until_it_expires(monkeypatch):
    stub, asked = fake_vocabulary({"按钮"})
    monkeypatch.setattr(vocab_routes, "get_vocabulary_by_words", stub)

    assert call_lookup(["按钮"])["按钮"]["pinyin"] == "py-按钮"
    assert call_lookup(["按钮"])["按钮"]["pinyin"] == "py-按钮"
    assert len(asked) == 1

    monkeypatch.setattr(vocab_routes, "_WORD_CACHE_TTL", -1)
    assert call_lookup(["按钮"])["按钮"]["pinyin"] == "py-按钮"
    assert len(asked) == 2


def test_lookup_batch_ignores_blank_input():
    with app.test_request_context("/api/vocab/lookup-batch?words="):
        assert lookup_batch().get_json() == {}
