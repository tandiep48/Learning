import io
import os
import sys

from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from routes import vocab_routes


class FakeVoskModel:
    pass


def test_normalize_spoken_text_keeps_chinese():
    assert vocab_routes.normalize_spoken_text("\u4f60 \u597d!") == "\u4f60\u597d"


def test_score_spoken_word_exact_match(monkeypatch):
    monkeypatch.setattr(vocab_routes, "get_speaking_asr_model", lambda: FakeVoskModel())
    monkeypatch.setattr(vocab_routes, "convert_audio_to_vosk_wav", lambda audio_path: "converted.wav")
    monkeypatch.setattr(vocab_routes, "transcribe_with_vosk", lambda model, wav_path: "\u4f60\u597d")

    result = vocab_routes.score_spoken_word("\u4f60\u597d", "unused.webm")

    assert result["recognized_text"] == "\u4f60\u597d"
    assert result["expected_pinyin"] == "ni3 hao3"
    assert result["recognized_pinyin"] == "ni3 hao3"
    assert result["score"] == 100
    assert result["is_correct"] is True


def test_score_spoken_word_empty_transcription(monkeypatch):
    monkeypatch.setattr(vocab_routes, "get_speaking_asr_model", lambda: FakeVoskModel())
    monkeypatch.setattr(vocab_routes, "convert_audio_to_vosk_wav", lambda audio_path: "converted.wav")
    monkeypatch.setattr(vocab_routes, "transcribe_with_vosk", lambda model, wav_path: "")

    result = vocab_routes.score_spoken_word("\u4f60\u597d", "unused.webm")

    assert result["recognized_text"] == ""
    assert result["score"] == 0
    assert result["is_correct"] is False


def test_speaking_endpoint_requires_audio():
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.register_blueprint(vocab_routes.vocab_bp)

    with app.test_client() as client:
        response = client.post("/api/vocab/speaking/score", data={"word": "\u4f60\u597d"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing audio recording."


def test_speaking_endpoint_does_not_call_progress_insert(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.register_blueprint(vocab_routes.vocab_bp)
    monkeypatch.setattr(vocab_routes, "score_spoken_word", lambda word, audio_path: {
        "recognized_text": "\u4f60\u597d",
        "expected_pinyin": "ni3 hao3",
        "recognized_pinyin": "ni3 hao3",
        "score": 100,
        "threshold": 80,
        "is_correct": True,
    })

    def fail_insert(*args, **kwargs):
        raise AssertionError("speaking endpoint must not write vocab_records")

    monkeypatch.setattr(vocab_routes, "insert_learning_progress", fail_insert)

    data = {
        "word": "\u4f60\u597d",
        "audio": (io.BytesIO(b"fake audio"), "attempt.webm"),
    }
    with app.test_client() as client:
        response = client.post("/api/vocab/speaking/score", data=data, content_type="multipart/form-data")

    assert response.status_code == 200
    assert response.get_json()["is_correct"] is True
