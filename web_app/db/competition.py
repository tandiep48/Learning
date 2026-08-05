"""
db/competition.py
------------------
Queries for the multiplayer "Learn Together" feature — competition rooms,
sessions, sections, questions, answers, scores and chat.
Extracted from the former monolithic db.py.
"""

import json
from psycopg2.extras import Json


def resolve_room_words(conn, passage_ids):
    """Union the vocabulary of the selected passages into a deduped word list
    (rows as returned by get_passage_vocab, keyed by 'cn'). Shared by room
    creation (word count) and answer validation."""
    from db.content import get_passage_vocab
    if not conn or not passage_ids:
        return []
    collected = []
    seen = set()
    for pid in passage_ids:
        for row in get_passage_vocab(conn, pid):
            cn = row.get("cn")
            if cn and cn not in seen:
                seen.add(cn)
                collected.append(row)
    return collected

def create_competition_room(conn, room_code, host_user_id, level, passage_ids, word_count, max_users, section_timeout_minutes):
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO competition_rooms
                    (room_code, host_user_id, category, level, passage_ids, word_count,
                     max_users, section_timeout_minutes, status)
                VALUES (%s, %s, 'vocab', %s, %s, %s, %s, %s, 'waiting')
                RETURNING id
            """, (room_code, host_user_id, level, Json(list(passage_ids)), word_count,
                  max_users, section_timeout_minutes))
            room_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO competition_room_members (room_id, user_id, role, status)
                VALUES (%s, %s, 'host', 'online')
                ON CONFLICT (room_id, user_id)
                DO UPDATE SET role = 'host', status = 'online',
                              left_at = NULL, last_seen_at = CURRENT_TIMESTAMP
            """, (room_id, host_user_id))
        conn.commit()
        return get_competition_room_by_code(conn, room_code)
    except Exception as e:
        print(f"Database create_competition_room failed: {e}")
        conn.rollback()
        return None

def get_competition_room_by_code(conn, room_code):
    if not conn or not room_code:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, room_code, host_user_id, level, passage_ids, word_count,
                       max_users, section_timeout_minutes, status, created_at, updated_at
                FROM competition_rooms
                WHERE room_code = %s
            """, (str(room_code).upper(),))
            row = cur.fetchone()
            if not row:
                return None
            passage_ids = row[4]
            if isinstance(passage_ids, str):
                passage_ids = json.loads(passage_ids)
            return {
                "id": row[0],
                "room_code": row[1],
                "host_user_id": row[2],
                "level": row[3],
                "passage_ids": passage_ids or [],
                "word_count": row[5],
                "max_users": row[6],
                "section_timeout_minutes": row[7],
                "status": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
                "updated_at": row[10].isoformat() if row[10] else None,
            }
    except Exception as e:
        print(f"Database get_competition_room_by_code failed: {e}")
        return None

def join_competition_room(conn, room_code, user_id):
    room = get_competition_room_by_code(conn, room_code)
    if not conn or not room:
        return None, "Room not found"
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM competition_room_members
                WHERE room_id = %s AND status != 'left'
            """, (room["id"],))
            active_count = int(cur.fetchone()[0] or 0)
            cur.execute("""
                SELECT 1 FROM competition_room_members
                WHERE room_id = %s AND user_id = %s
            """, (room["id"], user_id))
            already_member = cur.fetchone() is not None
            if not already_member and active_count >= int(room["max_users"] or 8):
                return None, "Room is full"

            role = 'host' if int(room["host_user_id"]) == int(user_id) else 'participant'
            cur.execute("""
                INSERT INTO competition_room_members (room_id, user_id, role, status)
                VALUES (%s, %s, %s, 'online')
                ON CONFLICT (room_id, user_id)
                DO UPDATE SET status = 'online', left_at = NULL,
                              last_seen_at = CURRENT_TIMESTAMP
            """, (room["id"], user_id, role))
        conn.commit()
        return get_competition_room_state(conn, room_code), None
    except Exception as e:
        print(f"Database join_competition_room failed: {e}")
        conn.rollback()
        return None, "Could not join room"

def leave_competition_room(conn, room_code, user_id):
    room = get_competition_room_by_code(conn, room_code)
    if not conn or not room:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE competition_room_members
                SET status = 'left', left_at = CURRENT_TIMESTAMP,
                    last_seen_at = CURRENT_TIMESTAMP
                WHERE room_id = %s AND user_id = %s
            """, (room["id"], user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database leave_competition_room failed: {e}")
        conn.rollback()
        return False

def get_competition_room_state(conn, room_code):
    room = get_competition_room_by_code(conn, room_code)
    if not conn or not room:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.user_id, u.username, m.role, m.status, m.joined_at
                FROM competition_room_members m
                JOIN users u ON u.id = m.user_id
                WHERE m.room_id = %s AND m.status != 'left'
                ORDER BY CASE WHEN m.role = 'host' THEN 0 ELSE 1 END, m.joined_at
            """, (room["id"],))
            members = [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "role": row[2],
                    "status": row[3],
                    "joined_at": row[4].isoformat() if row[4] else None,
                }
                for row in cur.fetchall()
            ]
            cur.execute("""
                SELECT c.id, c.user_id, u.username, c.message, c.created_at
                FROM competition_chat_messages c
                JOIN users u ON u.id = c.user_id
                WHERE c.room_id = %s
                ORDER BY c.created_at DESC
                LIMIT 50
            """, (room["id"],))
            chat = [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "username": row[2],
                    "message": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                }
                for row in reversed(cur.fetchall())
            ]
            cur.execute("""
                SELECT id, status, current_section, section_started_at, section_ends_at,
                       started_at, finished_at
                FROM competition_sessions
                WHERE room_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (room["id"],))
            session_row = cur.fetchone()
            session = None
            if session_row:
                session = {
                    "id": session_row[0],
                    "status": session_row[1],
                    "current_section": session_row[2],
                    "section_started_at": session_row[3].isoformat() if session_row[3] else None,
                    "section_ends_at": session_row[4].isoformat() if session_row[4] else None,
                    "started_at": session_row[5].isoformat() if session_row[5] else None,
                    "finished_at": session_row[6].isoformat() if session_row[6] else None,
                }
        room["members"] = members
        room["chat"] = chat
        room["session"] = session
        return room
    except Exception as e:
        print(f"Database get_competition_room_state failed: {e}")
        return None

def add_competition_chat_message(conn, room_code, user_id, message):
    room = get_competition_room_by_code(conn, room_code)
    text = str(message or "").strip()[:1000]
    if not conn or not room or not text:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO competition_chat_messages (room_id, user_id, message)
                VALUES (%s, %s, %s)
                RETURNING id, created_at
            """, (room["id"], user_id, text))
            row = cur.fetchone()
            cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
            user_row = cur.fetchone()
        conn.commit()
        return {
            "id": row[0],
            "user_id": user_id,
            "username": user_row[0] if user_row else "User",
            "message": text,
            "created_at": row[1].isoformat() if row[1] else None,
        }
    except Exception as e:
        print(f"Database add_competition_chat_message failed: {e}")
        conn.rollback()
        return None

def start_competition_session(conn, room_code, host_user_id):
    room = get_competition_room_by_code(conn, room_code)
    if not conn or not room:
        return None, "Room not found"
    if int(room["host_user_id"]) != int(host_user_id):
        return None, "Only the host can start"
    if room["status"] == "running":
        return None, "Room is already running"
    if not room.get("passage_ids"):
        return None, "No vocabulary selected"

    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE competition_rooms
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (room["id"],))
            cur.execute("""
                INSERT INTO competition_sessions
                    (room_id, status, current_section, section_started_at, section_ends_at,
                     started_at)
                VALUES (
                    %s, 'running', 'vocab', CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP + (%s || ' minutes')::interval,
                    CURRENT_TIMESTAMP
                )
                RETURNING id
            """, (room["id"], int(room["section_timeout_minutes"] or 15)))
            session_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO competition_scores (session_id, user_id)
                SELECT %s, user_id
                FROM competition_room_members
                WHERE room_id = %s AND status != 'left'
                ON CONFLICT (session_id, user_id) DO NOTHING
            """, (session_id, room["id"]))
        conn.commit()
        return get_competition_session_state(conn, session_id), None
    except Exception as e:
        print(f"Database start_competition_session failed: {e}")
        conn.rollback()
        return None, "Could not start session"

def get_active_competition_session(conn, room_code):
    room = get_competition_room_by_code(conn, room_code)
    if not conn or not room:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id
                FROM competition_sessions
                WHERE room_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (room["id"],))
            row = cur.fetchone()
            return get_competition_session_state(conn, row[0]) if row else None
    except Exception as e:
        print(f"Database get_active_competition_session failed: {e}")
        return None

def get_competition_session_state(conn, session_id):
    if not conn or not session_id:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, s.room_id, r.room_code, s.status, s.current_section,
                       s.section_started_at, s.section_ends_at, s.started_at, s.finished_at
                FROM competition_sessions s
                JOIN competition_rooms r ON r.id = s.room_id
                WHERE s.id = %s
            """, (session_id,))
            row = cur.fetchone()
            if not row:
                return None
            state = {
                "id": row[0],
                "room_id": row[1],
                "room_code": row[2],
                "status": row[3],
                "current_section": row[4],
                "section_started_at": row[5].isoformat() if row[5] else None,
                "section_ends_at": row[6].isoformat() if row[6] else None,
                "started_at": row[7].isoformat() if row[7] else None,
                "finished_at": row[8].isoformat() if row[8] else None,
            }
            state["scores"] = get_competition_scores(conn, session_id)
            return state
    except Exception as e:
        print(f"Database get_competition_session_state failed: {e}")
        return None

# Per-mode scoring: base points + a time-decay speed bonus, minus a per-error penalty
# on the matching modes. Time uses fractional seconds; typing is binary (an incorrect
# submission scores nothing). See the scoring spec for the rationale behind each value.
MODE_CONFIG = {
    "typing":  {"base": 120, "max_bonus": 60, "decay": 5.0, "penalty_rate": 0.0},
    "listen":  {"base": 100, "max_bonus": 50, "decay": 2.0, "penalty_rate": 0.10},
    "meaning": {"base": 80,  "max_bonus": 40, "decay": 3.0, "penalty_rate": 0.10},
}

def calculate_competition_points(activity_type, is_correct, response_time_ms, wrong_attempts=0):
    cfg = MODE_CONFIG.get(activity_type)
    if not cfg:
        return 0
    # Typing accuracy is binary: an incorrect submission yields nothing.
    if cfg["penalty_rate"] == 0.0 and not is_correct:
        return 0
    seconds = max(0.0, int(response_time_ms or 0) / 1000.0)
    penalty = max(0, int(wrong_attempts or 0)) * (cfg["base"] * cfg["penalty_rate"])
    bonus = max(0.0, cfg["max_bonus"] - (seconds * cfg["decay"]))
    return max(0, round((cfg["base"] - penalty) + bonus))

def record_competition_vocab_answer(conn, session_id, user_id, word, activity_type, is_correct, response_time_ms, wrong_attempts=0):
    """Record one participant's answer for a word/activity, awarding points per the
    per-mode scoring rules (speed bonus, minus per-error penalties on the matching
    modes). One-shot per (word, activity_type); the client reports correctness, timing
    and wrong-attempt count, matching the solo trainer's trust model."""
    if not conn:
        return None, "Database unavailable"
    word = str(word or "").strip()
    activity_type = str(activity_type or "").strip()
    if not word or activity_type not in ("typing", "listen", "meaning"):
        return None, "Invalid answer payload"
    try:
        with conn.cursor() as cur:
            # Only accept answers while the session is running and the user is a scored participant.
            cur.execute("""
                SELECT 1
                FROM competition_sessions s
                JOIN competition_scores sc ON sc.session_id = s.id AND sc.user_id = %s
                WHERE s.id = %s AND s.status = 'running'
            """, (user_id, session_id))
            if not cur.fetchone():
                return None, "Session is not active"

            is_correct = bool(is_correct)
            points = calculate_competition_points(activity_type, is_correct, response_time_ms, wrong_attempts)
            cur.execute("""
                INSERT INTO competition_vocab_answers
                    (session_id, user_id, word, activity_type, is_correct, response_time_ms, points)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, user_id, word, activity_type) DO NOTHING
                RETURNING id
            """, (session_id, user_id, word, activity_type, is_correct,
                  int(response_time_ms or 0), points))
            inserted = cur.fetchone()
            if not inserted:
                return None, "Answer already submitted"
            cur.execute("""
                UPDATE competition_scores
                SET total_points = total_points + %s,
                    total_response_time_ms = total_response_time_ms + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s AND user_id = %s
            """, (points, int(response_time_ms or 0), session_id, user_id))
        conn.commit()
        return {
            "is_correct": is_correct,
            "points": points,
            "scores": get_competition_scores(conn, session_id),
        }, None
    except Exception as e:
        print(f"Database record_competition_vocab_answer failed: {e}")
        conn.rollback()
        return None, "Could not record answer"

def get_competition_scores(conn, session_id):
    if not conn or not session_id:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sc.user_id, u.username, sc.listening_points, sc.reading_points,
                       sc.total_points, sc.total_response_time_ms, sc.rank, sc.finished_at
                FROM competition_scores sc
                JOIN users u ON u.id = sc.user_id
                WHERE sc.session_id = %s
                ORDER BY sc.total_points DESC, sc.total_response_time_ms ASC, u.username
            """, (session_id,))
            return [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "listening_points": row[2],
                    "reading_points": row[3],
                    "total_points": row[4],
                    "total_response_time_ms": row[5],
                    "rank": row[6],
                    "finished_at": row[7].isoformat() if row[7] else None,
                }
                for row in cur.fetchall()
            ]
    except Exception as e:
        print(f"Database get_competition_scores failed: {e}")
        return []

def mark_competition_participant_finished(conn, session_id, user_id):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE competition_scores
                SET finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s AND user_id = %s AND finished_at IS NULL
            """, (session_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database mark_competition_participant_finished failed: {e}")
        conn.rollback()
        return False

def competition_all_participants_finished(conn, session_id):
    """True when every scored participant has reported finishing their run."""
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE finished_at IS NOT NULL) AS done
                FROM competition_scores
                WHERE session_id = %s
            """, (session_id,))
            total, done = cur.fetchone()
            return bool(total) and int(total) == int(done or 0)
    except Exception as e:
        print(f"Database competition_all_participants_finished failed: {e}")
        return False

def finalize_competition_session(conn, session_id):
    """Rank participants, mark the session ranked and free the room back to waiting.
    Called when everyone has finished or the room timer expires. Idempotent: a
    session already ranked is returned as-is."""
    state = get_competition_session_state(conn, session_id)
    if not conn or not state:
        return None
    if state["status"] == "ranked":
        return state
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE competition_sessions
                SET status = 'ranked', finished_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (session_id,))
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               ORDER BY total_points DESC,
                                        total_response_time_ms ASC,
                                        COALESCE(finished_at, CURRENT_TIMESTAMP) ASC
                           ) AS next_rank
                    FROM competition_scores
                    WHERE session_id = %s
                )
                UPDATE competition_scores sc
                SET rank = ranked.next_rank,
                    updated_at = CURRENT_TIMESTAMP
                FROM ranked
                WHERE sc.id = ranked.id
            """, (session_id,))
            cur.execute("""
                UPDATE competition_rooms r
                SET status = 'waiting', updated_at = CURRENT_TIMESTAMP
                FROM competition_sessions s
                WHERE s.id = %s AND r.id = s.room_id
            """, (session_id,))
        conn.commit()
        return get_competition_session_state(conn, session_id)
    except Exception as e:
        print(f"Database finalize_competition_session failed: {e}")
        conn.rollback()
        return None
