import random
import string

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from db import (
    create_competition_room,
    get_competition_room_state,
    get_competition_scores,
    resolve_room_words,
)


competition_bp = Blueprint("competition", __name__, url_prefix="/api/competition")


def make_room_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


@competition_bp.route("/rooms", methods=["POST"])
@login_required
def create_room():
    data = request.get_json(silent=True) or {}

    try:
        level = int(data.get("level"))
    except (TypeError, ValueError):
        return jsonify({"error": "HSK level is required"}), 400

    passage_ids = [str(p).strip() for p in (data.get("passage_ids") or []) if str(p).strip()]
    if not passage_ids:
        return jsonify({"error": "Select at least one lesson part"}), 400

    try:
        max_users = int(data.get("max_users", 8))
    except (TypeError, ValueError):
        max_users = 8
    max_users = min(30, max(2, max_users))

    try:
        section_timeout_minutes = int(data.get("section_timeout_minutes", 15))
    except (TypeError, ValueError):
        section_timeout_minutes = 15
    if section_timeout_minutes not in (5, 10, 15, 20):
        section_timeout_minutes = 15

    words = resolve_room_words(passage_ids)
    if not words:
        return jsonify({"error": "The selected parts have no vocabulary"}), 404

    room = None
    for _ in range(8):
        room_code = make_room_code()
        room = create_competition_room(
            room_code,
            current_user.id,
            level,
            passage_ids,
            len(words),
            max_users,
            section_timeout_minutes,
        )
        if room:
            break
    if not room:
        return jsonify({"error": "Could not create room"}), 500

    return jsonify({"room": get_competition_room_state(room["room_code"])})


@competition_bp.route("/rooms/<room_code>", methods=["GET"])
@login_required
def room_detail(room_code):
    room = get_competition_room_state(room_code.upper())
    if not room:
        return jsonify({"error": "Room not found"}), 404
    return jsonify({"room": room})


@competition_bp.route("/sessions/<int:session_id>/results", methods=["GET"])
@login_required
def session_results(session_id):
    return jsonify({"session_id": session_id, "scores": get_competition_scores(session_id)})
