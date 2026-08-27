"""
service/gcs_service.py
------------------------
Single point of contact for Google Cloud Storage. Routes must not read
GCS_BUCKET_URL / GCS_BUCKET_NAME or touch the storage client directly -
call the functions here instead, so the URL/object-naming rules and the
upload validation rules only live in one place.
"""

from __future__ import annotations

import logging
import os
import uuid

from werkzeug.utils import secure_filename

try:
    from google.cloud import storage
except Exception:
    storage = None

logger = logging.getLogger(__name__)


class GCSServiceError(Exception):
    """Raised for GCS configuration/validation/upload failures."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_AVATAR_BYTES = 3 * 1024 * 1024
_VALID_HSK_LEVELS = {'1', '2', '3', '4', '5', '6'}


def _bucket_url() -> str:
    return os.getenv('GCS_BUCKET_URL', '').rstrip('/')


def build_public_url(object_path: str) -> str | None:
    """Turn a stored object path into a public URL, or None if GCS isn't configured."""
    base_url = _bucket_url()
    if not base_url or not object_path:
        return None
    return f"{base_url}/{str(object_path).lstrip('/')}"


def avatar_url(avatar_path: str | None) -> str | None:
    if not avatar_path:
        return None
    return build_public_url(avatar_path)


def hsk_image_url(level) -> str:
    base_url = _bucket_url()
    if not base_url:
        return ''
    level_num = str(level).replace('HSK', '').replace('hsk', '').replace('H', '').replace('h', '')
    if level_num not in _VALID_HSK_LEVELS:
        return ''
    return f"{base_url}/hsk_images/hsk{level_num}.png"


def practice_image_url(category, level, filename) -> str | None:
    return build_public_url(f"images/{category}/{level}/{filename}")


def practice_audio_url(category, number, filename) -> str | None:
    return build_public_url(f"question_bank/{category}/{category}-{number}/{filename}")


def vocab_audio_url(filename) -> str | None:
    return build_public_url(f"vocab_audio/{filename}")


def lesson_audio_url(filename) -> str | None:
    return build_public_url(f"lesson_audio/{filename}")


def lesson_image_url(hsk, filename) -> str | None:
    # Convert formats like 'h1-lesson-2.png' to 'H1-lesson 2.png'
    formatted_filename = filename.lower().replace('-lesson-', '-lesson ')
    if formatted_filename.startswith(hsk.lower()):
        formatted_filename = hsk.upper() + formatted_filename[len(hsk):]
    return build_public_url(f"lesson_images/{hsk.upper()}/{formatted_filename}")


def lesson_cover_url(code) -> str | None:
    return build_public_url(f"lesson_cover/{code.upper()}.png")


def _allowed_avatar_extension(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


def upload_avatar(user_id, file_storage) -> str:
    """
    Validate and upload an avatar image to GCS.

    Returns the stored object path (not the public URL) - callers that need
    the URL should pass it to avatar_url().

    Raises:
        GCSServiceError(503): GCS client/bucket not configured.
        GCSServiceError(400): missing file, disallowed extension, or too large.
        GCSServiceError(500): the upload itself failed.
    """
    if storage is None:
        raise GCSServiceError("Google Cloud Storage client is not installed", 503)

    bucket_name = os.getenv('GCS_BUCKET_NAME')
    if not bucket_name:
        raise GCSServiceError("GCS_BUCKET_NAME is not configured", 503)

    if not file_storage or not file_storage.filename:
        raise GCSServiceError("Avatar file is required")

    if not _allowed_avatar_extension(file_storage.filename):
        raise GCSServiceError("Avatar must be png, jpg, jpeg, webp, or gif")

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_AVATAR_BYTES:
        raise GCSServiceError("Avatar must be 3MB or smaller")

    safe_name = secure_filename(file_storage.filename)
    ext = safe_name.rsplit('.', 1)[1].lower()
    object_name = f"avatars/user_{user_id}/{uuid.uuid4().hex}.{ext}"
    content_type = file_storage.mimetype or f"image/{ext}"

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_file(file_storage, content_type=content_type)
    except Exception:
        logger.exception("Avatar upload to GCS failed for user_id=%s object=%s", user_id, object_name)
        raise GCSServiceError("Avatar upload failed. Please try again.", 500)

    return object_name
