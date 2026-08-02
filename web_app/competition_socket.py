from flask_login import current_user
from flask_socketio import emit, join_room as socket_join_room, leave_room as socket_leave_room

from db import (
    add_competition_chat_message,
    competition_all_participants_finished,
    finalize_competition_session,
    get_active_competition_session,
    get_competition_room_state,
    get_competition_scores,
    get_db_connection,
    join_competition_room,
    leave_competition_room,
    mark_competition_participant_finished,
    record_competition_vocab_answer,
    start_competition_session,
)


socketio = None


def init_competition_socket(socketio_instance):
    global socketio
    socketio = socketio_instance
    register_handlers()


def authenticated():
    return bool(getattr(current_user, "is_authenticated", False))


def emit_error(message):
    emit("competition_error", {"error": message})


def broadcast_room_state(room_code):
    conn = get_db_connection()
    if not conn:
        return
    try:
        state = get_competition_room_state(conn, room_code)
        if state:
            socketio.emit("room_state", {"room": state}, to=room_code)
    finally:
        conn.close()


def emit_session_event(room_code, state):
    if not state:
        return
    if state["status"] == "ranked":
        socketio.emit("session_finished", {"session": state, "scores": state.get("scores", [])}, to=room_code)
        socketio.emit("ranking_update", {"scores": state.get("scores", [])}, to=room_code)
        broadcast_room_state(room_code)
    else:
        socketio.emit("session_started", {"session": state}, to=room_code)
        schedule_session_timeout(state)


def schedule_session_timeout(session_state):
    if not socketio or not session_state or session_state["status"] != "running":
        return
    if not session_state.get("section_ends_at"):
        return
    socketio.start_background_task(session_timeout_task, session_state["id"], session_state["room_code"])


def session_timeout_task(session_id, room_code):
    socketio.sleep(60)
    while True:
        conn = get_db_connection()
        if not conn:
            return
        try:
            state = get_active_competition_session(conn, room_code)
            if not state or state["id"] != session_id or state["status"] != "running":
                return

            from datetime import datetime, timezone
            ends_at_raw = state.get("section_ends_at")
            if not ends_at_raw:
                return
            ends_at = datetime.fromisoformat(ends_at_raw)
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= ends_at:
                final_state = finalize_competition_session(conn, session_id)
                emit_session_event(room_code, final_state)
                return
        finally:
            conn.close()
        socketio.sleep(15)


def maybe_finalize(conn, room_code, session_id):
    if competition_all_participants_finished(conn, session_id):
        final_state = finalize_competition_session(conn, session_id)
        emit_session_event(room_code, final_state)


def register_handlers():
    @socketio.on("join_room")
    def handle_join_room(data):
        if not authenticated():
            emit_error("Login required")
            return
        room_code = str((data or {}).get("room_code") or "").strip().upper()
        if not room_code:
            emit_error("Room code is required")
            return
        conn = get_db_connection()
        if not conn:
            emit_error("Database unavailable")
            return
        try:
            state, error = join_competition_room(conn, room_code, current_user.id)
            if error:
                emit_error(error)
                return
            socket_join_room(room_code)
            emit("joined_room", {"room": state})
            socketio.emit("room_state", {"room": state}, to=room_code)
            active = get_active_competition_session(conn, room_code)
            if active and active.get("status") == "running":
                emit("session_started", {"session": active})
            elif active and active.get("status") == "ranked":
                emit("session_finished", {"session": active, "scores": active.get("scores", [])})
        finally:
            conn.close()

    @socketio.on("leave_room")
    def handle_leave_room(data):
        if not authenticated():
            return
        room_code = str((data or {}).get("room_code") or "").strip().upper()
        if not room_code:
            return
        conn = get_db_connection()
        if conn:
            try:
                leave_competition_room(conn, room_code, current_user.id)
            finally:
                conn.close()
        socket_leave_room(room_code)
        broadcast_room_state(room_code)

    @socketio.on("chat_message")
    def handle_chat_message(data):
        if not authenticated():
            emit_error("Login required")
            return
        room_code = str((data or {}).get("room_code") or "").strip().upper()
        message = (data or {}).get("message") or ""
        conn = get_db_connection()
        if not conn:
            emit_error("Database unavailable")
            return
        try:
            chat = add_competition_chat_message(conn, room_code, current_user.id, message)
            if chat:
                socketio.emit("chat_message", chat, to=room_code)
        finally:
            conn.close()

    @socketio.on("host_start_session")
    def handle_host_start_session(data):
        if not authenticated():
            emit_error("Login required")
            return
        room_code = str((data or {}).get("room_code") or "").strip().upper()
        conn = get_db_connection()
        if not conn:
            emit_error("Database unavailable")
            return
        try:
            state, error = start_competition_session(conn, room_code, current_user.id)
            if error:
                emit_error(error)
                return
            emit_session_event(room_code, state)
            broadcast_room_state(room_code)
        finally:
            conn.close()

    @socketio.on("vocab_answer")
    def handle_vocab_answer(data):
        if not authenticated():
            emit_error("Login required")
            return
        payload = data or {}
        room_code = str(payload.get("room_code") or "").strip().upper()
        try:
            session_id = int(payload.get("session_id"))
        except (TypeError, ValueError):
            emit_error("Invalid answer payload")
            return

        conn = get_db_connection()
        if not conn:
            emit_error("Database unavailable")
            return
        try:
            result, error = record_competition_vocab_answer(
                conn,
                session_id,
                current_user.id,
                payload.get("word"),
                payload.get("activity_type"),
                payload.get("is_correct"),
                payload.get("response_time_ms", 0),
            )
            if error:
                # Duplicate / inactive answers are non-fatal; just don't broadcast.
                return
            socketio.emit("score_update", {"scores": result["scores"]}, to=room_code)
        finally:
            conn.close()

    @socketio.on("participant_finished")
    def handle_participant_finished(data):
        if not authenticated():
            emit_error("Login required")
            return
        payload = data or {}
        room_code = str(payload.get("room_code") or "").strip().upper()
        try:
            session_id = int(payload.get("session_id"))
        except (TypeError, ValueError):
            emit_error("Invalid session")
            return
        conn = get_db_connection()
        if not conn:
            emit_error("Database unavailable")
            return
        try:
            mark_competition_participant_finished(conn, session_id, current_user.id)
            socketio.emit("participant_waiting", {
                "user_id": current_user.id,
                "username": current_user.username,
            }, to=room_code)
            socketio.emit("score_update", {"scores": get_competition_scores(conn, session_id)}, to=room_code)
            maybe_finalize(conn, room_code, session_id)
        finally:
            conn.close()

    @socketio.on("return_to_lobby")
    def handle_return_to_lobby(data):
        room_code = str((data or {}).get("room_code") or "").strip().upper()
        if room_code:
            broadcast_room_state(room_code)
            socketio.emit("return_to_lobby", {}, to=room_code)
