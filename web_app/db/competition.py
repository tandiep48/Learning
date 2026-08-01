"""
db/competition.py
------------------
Queries for the multiplayer "Learn Together" feature — competition rooms,
sessions, sections, questions, answers, scores and chat.
Extracted from the former monolithic db.py.
"""

import json
from psycopg2.extras import Json


def get_competition_question_sets(conn, category='practice'):
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT category, level, lesson,
                       COUNT(*) AS question_count,
                       COUNT(*) FILTER (WHERE LOWER(skill::text) = 'listening') AS listening_count,
                       COUNT(*) FILTER (WHERE LOWER(skill::text) = 'reading') AS reading_count
                FROM question_bank
                WHERE category = %s
                GROUP BY category, level, lesson
                HAVING COUNT(*) FILTER (WHERE LOWER(skill::text) = 'listening') > 0
                   AND COUNT(*) FILTER (WHERE LOWER(skill::text) = 'reading') > 0
                ORDER BY level, lesson
            """, (category,))
            return [
                {
                    "category": row[0],
                    "level": row[1],
                    "lesson": row[2],
                    "question_count": int(row[3] or 0),
                    "listening_count": int(row[4] or 0),
                    "reading_count": int(row[5] or 0),
                }
                for row in cur.fetchall()
            ]
    except Exception as e:
        print(f"Database get_competition_question_sets failed: {e}")
        return []

def create_competition_room(conn, room_code, host_user_id, category, level, lesson, progress, max_users, section_timeout_minutes):
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO competition_rooms
                    (room_code, host_user_id, category, level, lesson, progress,
                     max_users, section_timeout_minutes, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'waiting')
                RETURNING id
            """, (room_code, host_user_id, category, level, lesson, progress,
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
                SELECT id, room_code, host_user_id, category, level, lesson, progress,
                       max_users, section_timeout_minutes, status, created_at, updated_at
                FROM competition_rooms
                WHERE room_code = %s
            """, (str(room_code).upper(),))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "room_code": row[1],
                "host_user_id": row[2],
                "category": row[3],
                "level": row[4],
                "lesson": row[5],
                "progress": row[6],
                "max_users": row[7],
                "section_timeout_minutes": row[8],
                "status": row[9],
                "created_at": row[10].isoformat() if row[10] else None,
                "updated_at": row[11].isoformat() if row[11] else None,
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

def fetch_competition_questions(conn, category, level, lesson, progress):
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            progress_filter = str(progress or "").strip().lower()
            query = """
                SELECT id, level, lesson, no, skill, type, content, question,
                       answer, audio_key, image, options, progress, unit_id, category
                FROM question_bank
                WHERE category = %s AND level = %s AND lesson = %s
            """
            params = [category, level, lesson]
            if progress_filter and progress_filter != "all":
                query += " AND progress = %s"
                params.append(progress)
            query += """
                ORDER BY CASE WHEN LOWER(skill::text) = 'listening' THEN 0 ELSE 1 END,
                         progress, no
            """
            cur.execute(query, params)
            cols = ['source_question_id', 'level', 'lesson', 'no', 'skill', 'type',
                    'content', 'question', 'answer', 'audio_key', 'image', 'options',
                    'progress', 'unit_id', 'category']
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"Database fetch_competition_questions failed: {e}")
        return []

def start_competition_session(conn, room_code, host_user_id):
    room = get_competition_room_by_code(conn, room_code)
    if not conn or not room:
        return None, "Room not found"
    if int(room["host_user_id"]) != int(host_user_id):
        return None, "Only the host can start"
    if room["status"] == "running":
        return None, "Room is already running"

    questions = fetch_competition_questions(
        conn, room["category"], room["level"], room["lesson"], room["progress"]
    )
    listening = [q for q in questions if str(q.get("skill") or "").lower() == "listening"]
    reading = [q for q in questions if str(q.get("skill") or "").lower() == "reading"]
    if not listening or not reading:
        return None, "Selected set must include listening and reading questions"

    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE competition_rooms
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (room["id"],))
            cur.execute("""
                INSERT INTO competition_sessions
                    (room_id, status, current_section, section_started_at, section_ends_at)
                VALUES (
                    %s, 'listening', 'listening', CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP + (%s || ' minutes')::interval
                )
                RETURNING id
            """, (room["id"], int(room["section_timeout_minutes"] or 15)))
            session_id = cur.fetchone()[0]

            for section, section_questions in (("listening", listening), ("reading", reading)):
                for idx, question in enumerate(section_questions, start=1):
                    payload = dict(question)
                    answer = str(payload.pop("answer") or "")
                    source_question_id = payload.get("source_question_id")
                    cur.execute("""
                        INSERT INTO competition_session_questions
                            (session_id, source_question_id, section, section_order,
                             question_payload, correct_answer)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (session_id, source_question_id, section, idx, Json(payload), answer))

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
            state["questions"] = get_competition_section_questions(conn, session_id, state["current_section"])
            state["scores"] = get_competition_scores(conn, session_id)
            return state
    except Exception as e:
        print(f"Database get_competition_session_state failed: {e}")
        return None

def get_competition_section_questions(conn, session_id, section):
    if not conn or not session_id or section not in ("listening", "reading"):
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, section, section_order, source_question_id,
                       question_payload, correct_answer
                FROM competition_session_questions
                WHERE session_id = %s AND section = %s
                ORDER BY section_order
            """, (session_id, section))
            questions = []
            for row in cur.fetchall():
                payload = row[4] or {}
                if isinstance(payload, str):
                    payload = json.loads(payload)
                payload = dict(payload)
                payload.update({
                    "session_question_id": row[0],
                    "section": row[1],
                    "section_order": row[2],
                    "source_question_id": row[3],
                })
                questions.append(payload)
            return questions
    except Exception as e:
        print(f"Database get_competition_section_questions failed: {e}")
        return []

def calculate_competition_points(is_correct, response_time_ms):
    if not is_correct:
        return 0
    seconds = max(0, int(response_time_ms or 0) // 1000)
    return 100 + max(0, 20 - seconds)

def record_competition_answer(conn, session_id, user_id, session_question_id, user_answer, response_time_ms):
    if not conn:
        return None, "Database unavailable"
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT q.correct_answer, q.section
                FROM competition_session_questions q
                JOIN competition_sessions s ON s.id = q.session_id
                JOIN competition_scores sc ON sc.session_id = s.id AND sc.user_id = %s
                WHERE q.id = %s AND q.session_id = %s
                  AND s.current_section = q.section
                  AND s.status IN ('listening', 'reading')
            """, (user_id, session_question_id, session_id))
            row = cur.fetchone()
            if not row:
                return None, "Question is not active"
            correct_answer, section = row
            is_correct = str(user_answer or "").strip().upper() == str(correct_answer or "").strip().upper()
            points = calculate_competition_points(is_correct, response_time_ms)
            cur.execute("""
                INSERT INTO competition_answers
                    (session_id, user_id, session_question_id, section, user_answer,
                     is_correct, response_time_ms, points)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, user_id, session_question_id) DO NOTHING
                RETURNING id
            """, (session_id, user_id, session_question_id, section, str(user_answer or ""),
                  is_correct, int(response_time_ms or 0), points))
            inserted = cur.fetchone()
            if not inserted:
                return None, "Answer already submitted"
            update_score_sql = """
                UPDATE competition_scores
                SET {section_col} = {section_col} + %s,
                    total_points = total_points + %s,
                    total_response_time_ms = total_response_time_ms + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s AND user_id = %s
            """.format(section_col="listening_points" if section == "listening" else "reading_points")
            cur.execute(update_score_sql, (points, points, int(response_time_ms or 0), session_id, user_id))
        conn.commit()
        return {
            "is_correct": is_correct,
            "points": points,
            "section": section,
            "scores": get_competition_scores(conn, session_id),
        }, None
    except Exception as e:
        print(f"Database record_competition_answer failed: {e}")
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

def mark_competition_section_finished(conn, session_id, user_id):
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
        print(f"Database mark_competition_section_finished failed: {e}")
        conn.rollback()
        return False

def competition_all_participants_finished_section(conn, session_id, section):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM competition_session_questions
                WHERE session_id = %s AND section = %s
            """, (session_id, section))
            question_count = int(cur.fetchone()[0] or 0)
            if question_count == 0:
                return False
            cur.execute("""
                SELECT sc.user_id,
                       COUNT(a.id) FILTER (WHERE a.section = %s) AS answers
                FROM competition_scores sc
                LEFT JOIN competition_answers a
                  ON a.session_id = sc.session_id AND a.user_id = sc.user_id
                WHERE sc.session_id = %s
                GROUP BY sc.user_id
            """, (section, session_id))
            rows = cur.fetchall()
            return bool(rows) and all(int(row[1] or 0) >= question_count for row in rows)
    except Exception as e:
        print(f"Database competition_all_participants_finished_section failed: {e}")
        return False

def advance_competition_section(conn, session_id):
    state = get_competition_session_state(conn, session_id)
    if not conn or not state:
        return None
    try:
        with conn.cursor() as cur:
            if state["current_section"] == "listening":
                cur.execute("""
                    UPDATE competition_sessions
                    SET status = 'reading',
                        current_section = 'reading',
                        section_started_at = CURRENT_TIMESTAMP,
                        section_ends_at = CURRENT_TIMESTAMP + (
                            SELECT (section_timeout_minutes || ' minutes')::interval
                            FROM competition_rooms WHERE id = competition_sessions.room_id
                        )
                    WHERE id = %s
                """, (session_id,))
                cur.execute("""
                    UPDATE competition_scores
                    SET finished_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = %s
                """, (session_id,))
            else:
                cur.execute("""
                    UPDATE competition_sessions
                    SET status = 'ranked',
                        finished_at = CURRENT_TIMESTAMP
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
        print(f"Database advance_competition_section failed: {e}")
        conn.rollback()
        return None
