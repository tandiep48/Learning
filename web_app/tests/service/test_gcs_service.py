import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from service import gcs_service
from service.gcs_service import GCSServiceError


class FakeFile:
    def __init__(self, filename, content=b"x" * 10, mimetype="image/png"):
        self.filename = filename
        self.mimetype = mimetype
        self._content = content
        self._pos = 0

    def seek(self, offset, whence=os.SEEK_SET):
        self._pos = len(self._content) if whence == os.SEEK_END else offset

    def tell(self):
        return self._pos


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

def test_build_public_url_without_bucket_configured(monkeypatch):
    monkeypatch.delenv("GCS_BUCKET_URL", raising=False)
    assert gcs_service.build_public_url("avatars/foo.png") is None


def test_build_public_url_strips_slashes(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com/bucket/")
    assert gcs_service.build_public_url("/avatars/foo.png") == "https://cdn.example.com/bucket/avatars/foo.png"


def test_avatar_url_none_when_no_path(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com")
    assert gcs_service.avatar_url(None) is None
    assert gcs_service.avatar_url("") is None


def test_avatar_url_builds_from_path(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com")
    assert gcs_service.avatar_url("avatars/user_1/pic.png") == "https://cdn.example.com/avatars/user_1/pic.png"


def test_hsk_image_url_valid_level(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com")
    assert gcs_service.hsk_image_url("HSK3") == "https://cdn.example.com/hsk_images/hsk3.png"


def test_hsk_image_url_invalid_level_returns_empty_string(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com")
    assert gcs_service.hsk_image_url("HSK9") == ""


def test_hsk_image_url_without_bucket_returns_empty_string(monkeypatch):
    monkeypatch.delenv("GCS_BUCKET_URL", raising=False)
    assert gcs_service.hsk_image_url("HSK3") == ""


def test_lesson_image_url_normalizes_filename(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com")
    url = gcs_service.lesson_image_url("h1", "h1-lesson-2.png")
    assert url == "https://cdn.example.com/lesson_images/H1/H1-lesson 2.png"


def test_lesson_cover_url(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com")
    assert gcs_service.lesson_cover_url("aml") == "https://cdn.example.com/lesson_cover/AML.png"


def test_practice_image_and_audio_urls(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_URL", "https://cdn.example.com")
    assert gcs_service.practice_image_url("practice", 3, "a.png") == \
        "https://cdn.example.com/images/practice/3/a.png"
    assert gcs_service.practice_audio_url("practice", 5, "a.mp3") == \
        "https://cdn.example.com/question_bank/practice/practice-5/a.mp3"
    assert gcs_service.vocab_audio_url("word.mp3") == "https://cdn.example.com/vocab_audio/word.mp3"
    assert gcs_service.lesson_audio_url("l.mp3") == "https://cdn.example.com/lesson_audio/l.mp3"


# ---------------------------------------------------------------------------
# upload_avatar
# ---------------------------------------------------------------------------

def test_upload_avatar_fails_when_client_not_installed(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "bucket")
    with patch.object(gcs_service, "storage", None):
        with pytest.raises(GCSServiceError) as exc:
            gcs_service.upload_avatar(1, FakeFile("a.png"))
    assert exc.value.status_code == 503


def test_upload_avatar_fails_when_bucket_not_configured(monkeypatch):
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    with patch.object(gcs_service, "storage", MagicMock()):
        with pytest.raises(GCSServiceError) as exc:
            gcs_service.upload_avatar(1, FakeFile("a.png"))
    assert exc.value.status_code == 503


def test_upload_avatar_requires_file(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "bucket")
    with patch.object(gcs_service, "storage", MagicMock()):
        with pytest.raises(GCSServiceError) as exc:
            gcs_service.upload_avatar(1, None)
    assert exc.value.status_code == 400


def test_upload_avatar_rejects_bad_extension(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "bucket")
    with patch.object(gcs_service, "storage", MagicMock()):
        with pytest.raises(GCSServiceError) as exc:
            gcs_service.upload_avatar(1, FakeFile("a.exe"))
    assert exc.value.status_code == 400


def test_upload_avatar_rejects_oversized_file(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "bucket")
    big_file = FakeFile("a.png", content=b"x" * (gcs_service.MAX_AVATAR_BYTES + 1))
    with patch.object(gcs_service, "storage", MagicMock()):
        with pytest.raises(GCSServiceError) as exc:
            gcs_service.upload_avatar(1, big_file)
    assert exc.value.status_code == 400


def test_upload_avatar_success_returns_object_name(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "bucket")
    mock_storage = MagicMock()
    mock_blob = MagicMock()
    mock_storage.Client.return_value.bucket.return_value.blob.return_value = mock_blob

    with patch.object(gcs_service, "storage", mock_storage):
        object_name = gcs_service.upload_avatar(42, FakeFile("a.png"))

    assert object_name.startswith("avatars/user_42/")
    assert object_name.endswith(".png")
    mock_blob.upload_from_file.assert_called_once()


def test_upload_avatar_wraps_upload_failure(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "bucket")
    mock_storage = MagicMock()
    mock_storage.Client.return_value.bucket.return_value.blob.return_value.upload_from_file.side_effect = RuntimeError("boom")

    with patch.object(gcs_service, "storage", mock_storage), \
         patch.object(gcs_service.logger, "exception") as mock_log:
        with pytest.raises(GCSServiceError) as exc:
            gcs_service.upload_avatar(1, FakeFile("a.png"))
    assert exc.value.status_code == 500
    assert "boom" not in exc.value.message
    mock_log.assert_called_once()
