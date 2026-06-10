import os
import uuid

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from db import (
    get_db_connection,
    get_profile_summary,
    get_recent_learning,
    set_recent_learning,
    update_user_avatar_path,
)

try:
    from google.cloud import storage
except Exception:
    storage = None


user_bp = Blueprint('user', __name__)

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_AVATAR_BYTES = 3 * 1024 * 1024


def avatar_url_from_path(avatar_path):
    if not avatar_path:
        return None
    base_url = os.getenv('GCS_BUCKET_URL', '').rstrip('/')
    if base_url:
        return f"{base_url}/{avatar_path.lstrip('/')}"
    return None


def serialize_current_user():
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "level": current_user.level,
        "avatar_path": getattr(current_user, 'avatar_path', None),
        "avatar_url": avatar_url_from_path(getattr(current_user, 'avatar_path', None)),
    }


def allowed_avatar(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_AVATAR_EXTENSIONS


@user_bp.route('/profile')
@login_required
def profile_page():
    return render_template('profile/profile.html')


@user_bp.route('/api/user/profile-summary', methods=['GET'])
@login_required
def profile_summary():
    conn = get_db_connection()
    try:
        summary = get_profile_summary(conn, current_user.id)
    finally:
        if conn:
            conn.close()
    summary["user"] = serialize_current_user()
    return jsonify(summary)


@user_bp.route('/api/user/recent-learning', methods=['GET'])
@login_required
def recent_learning_get():
    conn = get_db_connection()
    try:
        recent = get_recent_learning(conn, current_user.id)
    finally:
        if conn:
            conn.close()
    return jsonify({"recent": recent})


@user_bp.route('/api/user/recent-learning', methods=['POST'])
@login_required
def recent_learning_set():
    data = request.get_json(silent=True) or {}
    passage_id = data.get('passage_id')
    if not passage_id:
        return jsonify({"error": "passage_id is required"}), 400

    conn = get_db_connection()
    try:
        ok = set_recent_learning(conn, current_user.id, passage_id)
    finally:
        if conn:
            conn.close()

    if not ok:
        return jsonify({"error": "Could not save recent learning"}), 500
    return jsonify({"status": "success", "recent": {"passage_id": passage_id}})


@user_bp.route('/api/user/avatar', methods=['POST'])
@login_required
def upload_avatar():
    if storage is None:
        return jsonify({"error": "Google Cloud Storage client is not installed"}), 503

    bucket_name = os.getenv('GCS_BUCKET_NAME')
    if not bucket_name:
        return jsonify({"error": "GCS_BUCKET_NAME is not configured"}), 503

    file = request.files.get('avatar')
    if not file or not file.filename:
        return jsonify({"error": "Avatar file is required"}), 400

    if not allowed_avatar(file.filename):
        return jsonify({"error": "Avatar must be png, jpg, jpeg, webp, or gif"}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_AVATAR_BYTES:
        return jsonify({"error": "Avatar must be 3MB or smaller"}), 400

    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit('.', 1)[1].lower()
    object_name = f"avatars/user_{current_user.id}/{uuid.uuid4().hex}.{ext}"

    content_type = file.mimetype or f"image/{ext}"
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_file(file, content_type=content_type)
    except Exception as e:
        return jsonify({"error": f"Avatar upload failed: {e}"}), 500

    conn = get_db_connection()
    try:
        ok = update_user_avatar_path(conn, current_user.id, object_name)
    finally:
        if conn:
            conn.close()

    if not ok:
        return jsonify({"error": "Avatar uploaded but profile could not be updated"}), 500

    current_user.avatar_path = object_name
    return jsonify({
        "status": "success",
        "avatar_path": object_name,
        "avatar_url": avatar_url_from_path(object_name),
    })
