import random
import string

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from db import (
    create_competition_room,
    get_competition_question_sets,
    get_competition_room_state,
    get_competition_scores,
    get_db_connection,
)


competition_bp = Blueprint("competition", __name__, url_prefix="/api/competition")


def normalize_category(value):
    return value if value in ("practice", "exam") else "practice"


def make_room_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


@competition_bp.route("/question-sets", methods=["GET"])
@login_required
def question_sets():
    category = normalize_category(request.args.get("category", "practice"))
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503
    try:
        return jsonify({"category": category, "sets": get_competition_question_sets(conn, category)})
    finally:
        conn.close()


@competition_bp.route("/rooms", methods=["POST"])
@login_required
def create_room():
    data = request.get_json(silent=True) or {}
    category = normalize_category(data.get("category", "practice"))
    progress = "all"

    try:
        level = int(data.get("level"))
        lesson = int(data.get("lesson"))
    except (TypeError, ValueError):
        return jsonify({"error": "level and lesson are required"}), 400

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

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        available_sets = get_competition_question_sets(conn, category)
        selected = [
            item for item in available_sets
            if int(item["level"]) == level
            and int(item["lesson"]) == lesson
        ]
        if not selected:
            return jsonify({"error": "Selected lesson was not found or lacks listening and reading sections"}), 404

        room = None
        for _ in range(8):
            room_code = make_room_code()
            room = create_competition_room(
                conn,
                room_code,
                current_user.id,
                category,
                level,
                lesson,
                progress,
                max_users,
                section_timeout_minutes,
            )
            if room:
                break
        if not room:
            return jsonify({"error": "Could not create room"}), 500

        return jsonify({"room": get_competition_room_state(conn, room["room_code"])})
    finally:
        conn.close()


@competition_bp.route("/rooms/<room_code>", methods=["GET"])
@login_required
def room_detail(room_code):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503
    try:
        room = get_competition_room_state(conn, room_code.upper())
        if not room:
            return jsonify({"error": "Room not found"}), 404
        return jsonify({"room": room})
    finally:
        conn.close()


@competition_bp.route("/sessions/<int:session_id>/results", methods=["GET"])
@login_required
def session_results(session_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503
    try:
        return jsonify({"session_id": session_id, "scores": get_competition_scores(conn, session_id)})
    finally:
        conn.close()
