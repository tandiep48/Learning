"""
routes/chinese_stroke_info_routes.py
---------------------------------------
Read-only API Blueprint for the `chinese_stroke_info` table — per-word
stroke counts and derived stroke-difficulty scores.

All endpoints require an authenticated session.

Prefix: /api/chinese_stroke_info

Endpoints:
    GET /api/chinese_stroke_info/<cn>       -> single word lookup
    GET /api/chinese_stroke_info?words=...  -> batch lookup (comma-separated)
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required

from entity.chinese_stroke_info.service import (
    ChineseStrokeInfoServiceError,
    get_stroke_info,
    get_stroke_info_batch,
)

chinese_stroke_info_bp = Blueprint(
    "chinese_stroke_info", __name__, url_prefix="/api/chinese_stroke_info"
)


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _handle_service_error(exc: ChineseStrokeInfoServiceError):
    return _error(exc.message, exc.status_code)


# ---------------------------------------------------------------------------
# GET /api/chinese_stroke_info
# Query params: words (comma-separated Chinese words)
# ---------------------------------------------------------------------------
@chinese_stroke_info_bp.route("", methods=["GET"])
@login_required
def get_stroke_info_batch_endpoint():
    """Batch stroke-info lookup for a comma-separated list of Chinese words."""
    raw = request.args.get("words", "").strip()
    if not raw:
        return _error("Query param 'words' is required.", 400)

    words = [w for w in raw.split(",") if w]
    result = get_stroke_info_batch(words)
    return _ok(result, 200)


# ---------------------------------------------------------------------------
# GET /api/chinese_stroke_info/<cn>
# ---------------------------------------------------------------------------
@chinese_stroke_info_bp.route("/<cn>", methods=["GET"])
@login_required
def get_stroke_info_endpoint(cn: str):
    """Stroke info for a single Chinese word."""
    try:
        result = get_stroke_info(cn)
        return _ok(result, 200)
    except ChineseStrokeInfoServiceError as exc:
        return _handle_service_error(exc)
