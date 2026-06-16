import os
import re
import uuid

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from db import (
    get_db_connection,
    get_mastered_words_page,
    get_passage_vocab,
    get_profile_summary,
    get_recent_learning,
    set_recent_learning,
    update_user_avatar_path,
    update_user_password,
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


def parse_dashboard_passage_id(passage_id):
    match = re.match(r"^H(\d+)_(\d+)_(\d+)$", str(passage_id or ""))
    if not match:
        return None
    level, lesson, part = match.groups()
    return {
        "level": int(level),
        "hsk_level": f"HSK{level}",
        "passage_prefix": f"H{level}",
        "lesson": int(lesson),
        "part": int(part),
    }


def clean_dashboard_value(value):
    return "" if value is None else value


def normalize_dashboard_vocab_row(row):
    word = clean_dashboard_value(row.get("word", row.get("cn", "")))
    return {
        "word": word,
        "cn": word,
        "pinyin": clean_dashboard_value(row.get("pinyin", "")),
        "meaning_vn": clean_dashboard_value(row.get("meaning_vn", "")),
        "meaning_en": clean_dashboard_value(row.get("meaning_en", "")),
        "audio_key": clean_dashboard_value(row.get("audio_key", "")),
        "level": clean_dashboard_value(row.get("level", row.get("hsk_level", ""))),
    }


def paginate_dashboard_rows(rows, page, page_size):
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    return rows[start:start + page_size], total, total_pages, page


def format_dashboard_duration(ms):
    seconds = round((int(ms or 0)) / 1000)
    if seconds < 60:
        return f"{seconds}s"
    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s" if remaining_seconds else f"{minutes}m"
    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"


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


@user_bp.route('/api/user/learned-vocab', methods=['GET'])
@login_required
def learned_vocab_page():
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', 24))
    except (TypeError, ValueError):
        page_size = 24

    conn = get_db_connection()
    try:
        result = get_mastered_words_page(conn, current_user.id, page, page_size)
    finally:
        if conn:
            conn.close()
    return jsonify(result)


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


@user_bp.route('/api/user/dashboard-current-lesson', methods=['GET'])
@login_required
def dashboard_current_lesson():
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', 12))
    except (TypeError, ValueError):
        page_size = 12
    page_size = min(50, max(5, page_size))

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        recent = get_recent_learning(conn, current_user.id)
        if not recent or not recent.get("passage_id"):
            return jsonify({"has_recent": False, "recent": None})

        parsed = parse_dashboard_passage_id(recent["passage_id"])
        if not parsed:
            return jsonify({"error": "Recent lesson has an unsupported passage id."}), 400

        lesson_pattern = f"{parsed['passage_prefix']}_{parsed['lesson']}_%"
        with conn.cursor() as cur:
            cur.execute("""
                SELECT passage_id
                FROM lesson_passages
                WHERE passage_id LIKE %s
                ORDER BY passage_id
            """, (lesson_pattern,))
            passage_ids = [row[0] for row in cur.fetchall()]

        if not passage_ids:
            passage_ids = [recent["passage_id"]]

        vocab_rows = []
        seen_words = set()
        for passage_id in passage_ids:
            for row in get_passage_vocab(conn, passage_id):
                normalized = normalize_dashboard_vocab_row(row)
                word = normalized.get("word")
                if word and word not in seen_words:
                    vocab_rows.append(normalized)
                    seen_words.add(word)

        page_rows, total, total_pages, page = paginate_dashboard_rows(vocab_rows, page, page_size)

        mode_names = {1: "meaning", 2: "typing", 3: "reorder", 4: "listening"}
        with conn.cursor() as cur:
            cur.execute("""
                SELECT mode,
                       COUNT(*) AS attempts,
                       COALESCE(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END), 0) AS correct,
                       COALESCE(SUM(response_time_ms), 0)::bigint AS time_ms
                FROM lesson_records
                WHERE user_id = %s
                  AND passage_id = ANY(%s)
                GROUP BY mode
                ORDER BY mode
            """, (current_user.id, passage_ids))
            progress_modes = []
            for row in cur.fetchall():
                attempts = int(row[1] or 0)
                correct = int(row[2] or 0)
                time_ms = int(row[3] or 0)
                progress_modes.append({
                    "mode": mode_names.get(row[0], str(row[0])),
                    "attempts": attempts,
                    "correct": correct,
                    "accuracy_pct": round((correct / attempts) * 100) if attempts else 0,
                    "time_ms": time_ms,
                    "time_label": format_dashboard_duration(time_ms),
                })

        total_attempts = sum(item["attempts"] for item in progress_modes)
        total_correct = sum(item["correct"] for item in progress_modes)
        total_time_ms = sum(item["time_ms"] for item in progress_modes)

        return jsonify({
            "has_recent": True,
            "recent": recent,
            "lesson": {
                "passage_id": recent["passage_id"],
                "hsk_level": parsed["hsk_level"],
                "level": parsed["level"],
                "lesson": parsed["lesson"],
                "part": parsed["part"],
                "passage_ids": passage_ids,
                "updated_at": recent.get("updated_at"),
            },
            "vocab": {
                "rows": page_rows,
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
            "progress": {
                "modes": progress_modes,
                "attempts": total_attempts,
                "correct": total_correct,
                "accuracy_pct": round((total_correct / total_attempts) * 100) if total_attempts else 0,
                "time_ms": total_time_ms,
                "time_label": format_dashboard_duration(total_time_ms),
            },
        })
    finally:
        conn.close()


@user_bp.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username') or '').strip()
    new_password = str(data.get('new_password') or '')

    if not username or not new_password:
        return jsonify({"error": "Username and new password are required."}), 400

    if username != current_user.username:
        return jsonify({"error": "Username does not match the logged-in account."}), 403

    password_hash = generate_password_hash(new_password)
    conn = get_db_connection()
    try:
        ok = update_user_password(conn, current_user.id, password_hash)
    finally:
        if conn:
            conn.close()

    if not ok:
        return jsonify({"error": "Could not update password."}), 500

    return jsonify({"status": "success"})


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
