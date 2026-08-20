import random
import string

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from db import (
    create_competition_room,
    get_competition_room_state,
    get_competition_scores,
    prepare_room_settings,
)


competition_bp = Blueprint("competition", __name__, url_prefix="/api/competition")

# Validation errors that mean "the picked passages have no material" map to 404.
ROOM_EMPTY_ERRORS = (
    "The selected parts have no vocabulary",
    "The selected lessons have no tasks",
)


def make_room_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


@competition_bp.route("/rooms", methods=["POST"])
@login_required
def create_room():
    data = request.get_json(silent=True) or {}
    settings, error = prepare_room_settings(data)
    if error:
        return jsonify({"error": error}), 404 if error in ROOM_EMPTY_ERRORS else 400

    room = None
    for _ in range(8):
        room_code = make_room_code()
        room = create_competition_room(
            room_code,
            current_user.id,
            settings["level"],
            settings["passage_ids"],
            settings["source_count"],
            settings["max_users"],
            settings["section_timeout_minutes"],
            category=settings["category"],
            activity_type=settings["activity_type"],
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
