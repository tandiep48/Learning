import os
import json
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

load_dotenv()

# --- DATABASE CONFIG (loaded from .env) ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'chinese')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASSWORD', 'admin')

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")
        print("Progress will not be saved.")
        return None

def insert_learning_progress(conn, user_id, session_id, mode, word, round_num, game_info, user_answer, is_correct, response_time_ms, updated_at):
    if not conn:
        return
        
    query = """
        INSERT INTO vocab_records 
        (user_id, session_id, mode, word, round_num, game_info, user_answer, is_correct, response_time_ms, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (
                user_id, str(session_id), mode, word, round_num, 
                game_info, user_answer, is_correct, response_time_ms, updated_at
            ))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Database insert failed: {e}")
        conn.rollback()

def insert_lesson_progress(conn, user_id, session_id, passage_id, line_id, mode, game_info, user_answer, is_correct, response_time_ms, updated_at):
    if not conn:
        return
        
    query = """
        INSERT INTO lesson_records 
        (user_id, session_id, passage_id, line_id, mode, game_info, user_answer, is_correct, response_time_ms, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (
                user_id, str(session_id), passage_id, line_id, mode, 
                game_info, user_answer, is_correct, response_time_ms, updated_at
            ))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Database lesson insert failed: {e}")
        conn.rollback()

def insert_practice_progress(conn, user_id, session_id, hsk_level, lesson, question_no, skill, question_type, user_answer, is_correct, response_time_ms=None, category='practice'):
    if not conn:
        return
        
    query = """
        INSERT INTO practice_record 
        (user_id, session_id, hsk_level, lesson, question_no, skill, question_type, user_answer, is_correct, response_time_ms, category)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (
                user_id, str(session_id), hsk_level, str(lesson), question_no, skill, question_type, user_answer, is_correct, response_time_ms, category or 'practice'
            ))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Database practice insert failed: {e}")
        conn.rollback()

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

def set_recent_learning(conn, user_id, passage_id):
    if not conn or not passage_id:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_learning_state (user_id, current_passage_id, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET current_passage_id = EXCLUDED.current_passage_id,
                              updated_at = CURRENT_TIMESTAMP
            """, (user_id, passage_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ Database set_recent_learning failed: {e}")
        conn.rollback()
        return False

def get_recent_learning(conn, user_id):
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT current_passage_id, updated_at
                FROM user_learning_state
                WHERE user_id = %s
            """, (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {"passage_id": row[0], "updated_at": row[1].isoformat() if row[1] else None}
    except Exception as e:
        print(f"⚠️ Database get_recent_learning failed: {e}")
        return None

def mark_lesson_part_completed(conn, user_id, passage_id):
    if not conn or not passage_id:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_lesson_part_progress
                    (user_id, passage_id, lesson_trainer_completed_at, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, passage_id)
                DO UPDATE SET lesson_trainer_completed_at = CURRENT_TIMESTAMP,
                              updated_at = CURRENT_TIMESTAMP
            """, (user_id, passage_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database mark_lesson_part_completed failed: {e}")
        conn.rollback()
        return False

def get_lesson_picker_progress(conn, user_id, hsk_level):
    if not conn:
        return {"lessons": {}, "parts": {}}

    try:
        mastered_words = set(get_learned_words(conn, user_id))

        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.passage_id, pv.cn
                FROM lesson_passages p
                LEFT JOIN passage_vocabulary pv ON pv.passage_id = p.passage_id
                WHERE p.hsk_level = %s
                ORDER BY p.passage_id, pv.cn
            """, (hsk_level,))
            vocab_rows = cur.fetchall()

            cur.execute("""
                SELECT passage_id
                FROM user_lesson_part_progress
                WHERE user_id = %s
                  AND lesson_trainer_completed_at IS NOT NULL
            """, (user_id,))
            completed_passages = {row[0] for row in cur.fetchall()}

        parts = {}
        lesson_words = {}
        lesson_passages = {}
        lesson_completed = {}

        for passage_id, word in vocab_rows:
            id_parts = str(passage_id or "").split("_")
            lesson_num = id_parts[1] if len(id_parts) >= 2 else "Other"

            part_progress = parts.setdefault(passage_id, {
                "passage_id": passage_id,
                "lesson": lesson_num,
                "total_words": 0,
                "learned_words": 0,
                "lesson_learned": 1 if passage_id in completed_passages else 0,
                "lesson_total": 1,
                "_words": set(),
                "_learned_word_set": set(),
            })
            words_for_lesson = lesson_words.setdefault(lesson_num, set())
            passages_for_lesson = lesson_passages.setdefault(lesson_num, set())
            completed_for_lesson = lesson_completed.setdefault(lesson_num, set())

            passages_for_lesson.add(passage_id)
            if passage_id in completed_passages:
                completed_for_lesson.add(passage_id)

            if word:
                part_progress["_words"].add(word)
                words_for_lesson.add(word)
                if word in mastered_words:
                    part_progress["_learned_word_set"].add(word)

        for item in parts.values():
            item["total_words"] = len(item.pop("_words", set()))
            item["learned_words"] = len(item.pop("_learned_word_set", set()))

        lessons = {}
        for lesson_num, words in lesson_words.items():
            passages = lesson_passages.get(lesson_num, set())
            completed = lesson_completed.get(lesson_num, set())
            lessons[lesson_num] = {
                "lesson": lesson_num,
                "total_words": len(words),
                "learned_words": len(words.intersection(mastered_words)),
                "lesson_learned": len(completed),
                "lesson_total": len(passages),
            }

        return {"lessons": lessons, "parts": parts}
    except Exception as e:
        print(f"Database get_lesson_picker_progress failed: {e}")
        return {"lessons": {}, "parts": {}}


def recompute_user_level(conn, user_id):
    """
    Derive and (if higher) persist the user's HSK level from their lesson-trainer
    completion. Level only ever increases (cap HSK 6). Two ways to qualify, and we take
    the highest:
      - Completion: finished every lesson part at levels 1..L  -> ready for level L+1.
      - Engagement: completed at least one full lesson (all its parts) at level H
        -> they can do level H, so jump straight to H.
    Passage ids look like H{level}_{lesson}_{part}. Returns the resulting level.
    """
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(r"""
                SELECT
                    (regexp_replace(split_part(lp.passage_id, '_', 1), '\D', '', 'g'))::int AS lvl,
                    split_part(lp.passage_id, '_', 2)                                       AS lesson,
                    COUNT(*)                                                                AS total_parts,
                    COUNT(ulp.passage_id)                                                   AS done_parts
                FROM lesson_passages lp
                LEFT JOIN user_lesson_part_progress ulp
                       ON ulp.passage_id = lp.passage_id
                      AND ulp.user_id = %s
                      AND ulp.lesson_trainer_completed_at IS NOT NULL
                WHERE lp.passage_id ~ '^H\d+_\d+_\d+$'
                GROUP BY 1, 2
            """, (user_id,))
            rows = cur.fetchall()

            cur.execute("SELECT level FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            current = int(row[0]) if row and row[0] else 1

        # Per level: is every lesson complete, and is at least one lesson complete?
        from collections import defaultdict
        level_lessons = defaultdict(list)
        for lvl, _lesson, total_parts, done_parts in rows:
            if lvl and 1 <= lvl <= 6:
                level_lessons[lvl].append((total_parts, done_parts))

        level_fully_complete = {}
        level_has_full_lesson = {}
        for lvl in range(1, 7):
            lessons = level_lessons.get(lvl, [])
            level_fully_complete[lvl] = bool(lessons) and all(d == t for t, d in lessons)
            level_has_full_lesson[lvl] = any(t > 0 and d == t for t, d in lessons)

        # Completion: highest level such that all of 1..L are fully done -> ready for L+1.
        completed_through = 0
        for lvl in range(1, 7):
            if level_fully_complete[lvl]:
                completed_through = lvl
            else:
                break
        completion_target = min(6, completed_through + 1) if completed_through >= 1 else 0

        # Engagement: highest level with at least one fully completed lesson.
        engagement_target = max(
            (lvl for lvl in range(1, 7) if level_has_full_lesson[lvl]),
            default=0,
        )

        target = max(current, completion_target, engagement_target)
        target = min(6, max(1, target))

        if target > current:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET level = %s WHERE id = %s", (target, user_id))
            conn.commit()
        return target
    except Exception as e:
        print(f"Database recompute_user_level failed: {e}")
        conn.rollback()
        return None


def update_user_avatar_path(conn, user_id, avatar_path):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET avatar_path = %s WHERE id = %s", (avatar_path, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ Database update_user_avatar_path failed: {e}")
        conn.rollback()
        return False

def get_user_hanzi_font(conn, user_id):
    if not conn:
        return "Noto Sans"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(hanzi_font, ''), 'Noto Sans') FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else "Noto Sans"
    except Exception as e:
        print(f"Database get_user_hanzi_font failed: {e}")
        conn.rollback()
        return "Noto Sans"

def update_user_hanzi_font(conn, user_id, hanzi_font):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET hanzi_font = %s WHERE id = %s", (hanzi_font, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database update_user_hanzi_font failed: {e}")
        conn.rollback()
        return False

def get_user_hanzi_script(conn, user_id):
    if not conn:
        return "simplified"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(hanzi_script, ''), 'simplified') FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else "simplified"
    except Exception as e:
        print(f"Database get_user_hanzi_script failed: {e}")
        conn.rollback()
        return "simplified"

def update_user_hanzi_script(conn, user_id, hanzi_script):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET hanzi_script = %s WHERE id = %s", (hanzi_script, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database update_user_hanzi_script failed: {e}")
        conn.rollback()
        return False

def get_user_ui_language(conn, user_id):
    if not conn:
        return "en"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(ui_language, ''), 'en') FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else "en"
    except Exception as e:
        print(f"Database get_user_ui_language failed: {e}")
        conn.rollback()
        return "en"

def update_user_ui_language(conn, user_id, ui_language):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET ui_language = %s WHERE id = %s", (ui_language, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database update_user_ui_language failed: {e}")
        conn.rollback()
        return False

def update_user_password(conn, user_id, password_hash):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password = %s WHERE id = %s", (password_hash, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ Database update_user_password failed: {e}")
        conn.rollback()
        return False

def get_profile_summary(conn, user_id):
    if not conn:
        return {
            "time_totals_ms": {"vocab": 0, "lesson": 0, "practice": 0, "exam": 0},
            "vocab_mode_time_ms": [],
            "lesson_mode_time_ms": [],
            "practice_skill_time_ms": []
        }

    summary = {
        "time_totals_ms": {"vocab": 0, "lesson": 0, "practice": 0, "exam": 0},
        "vocab_mode_time_ms": [],
        "lesson_mode_time_ms": [],
        "practice_skill_time_ms": []
    }

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT mode, COALESCE(SUM(response_time_ms), 0)::bigint
                FROM vocab_records
                WHERE user_id = %s AND response_time_ms IS NOT NULL
                GROUP BY mode
                ORDER BY mode
            """, (user_id,))
            rows = cur.fetchall()
            summary["vocab_mode_time_ms"] = [{"mode": row[0], "time_ms": int(row[1] or 0)} for row in rows]
            summary["time_totals_ms"]["vocab"] = sum(item["time_ms"] for item in summary["vocab_mode_time_ms"])
    except Exception as e:
        print(f"⚠️ Database vocab time summary failed: {e}")

    lesson_mode_names = {1: "meaning", 2: "typing", 3: "reorder", 4: "listening"}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT mode, COALESCE(SUM(response_time_ms), 0)::bigint
                FROM lesson_records
                WHERE user_id = %s AND response_time_ms IS NOT NULL
                GROUP BY mode
                ORDER BY mode
            """, (user_id,))
            rows = cur.fetchall()
            summary["lesson_mode_time_ms"] = [
                {"mode": lesson_mode_names.get(row[0], str(row[0])), "time_ms": int(row[1] or 0)}
                for row in rows
            ]
            summary["time_totals_ms"]["lesson"] = sum(item["time_ms"] for item in summary["lesson_mode_time_ms"])
    except Exception as e:
        print(f"⚠️ Database lesson time summary failed: {e}")

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(pr.category, 'practice') AS category,
                       COALESCE(pr.skill, 'unknown') AS skill,
                       COALESCE(SUM(pr.response_time_ms), 0)::bigint
                FROM practice_record pr
                WHERE pr.user_id = %s AND pr.response_time_ms IS NOT NULL
                GROUP BY COALESCE(pr.category, 'practice'), COALESCE(pr.skill, 'unknown')
                ORDER BY category, skill
            """, (user_id,))
            rows = cur.fetchall()
            summary["practice_skill_time_ms"] = [
                {"category": row[0], "skill": row[1], "time_ms": int(row[2] or 0)}
                for row in rows
            ]
            for item in summary["practice_skill_time_ms"]:
                category = item["category"] if item["category"] in ("practice", "exam") else "practice"
                summary["time_totals_ms"][category] += item["time_ms"]
    except Exception as e:
        print(f"⚠️ Database practice time summary failed: {e}")

    return summary

def get_learned_words(conn, user_id):
    """
    Returns a list of words that have been fully learned by the given user
    (3 correct modes in round 1).
    """
    if not conn:
        return []

    query = """
    WITH daily_attempts AS (
        SELECT 
            word,
            DATE(updated_at) as attempt_date,
            count(DISTINCT CASE WHEN is_correct = true THEN mode END) as successful_modes
        FROM vocab_records
        WHERE mode IN ('typing', 'listen', 'meaning')
          AND round_num = 1
          AND user_id = %s
        GROUP BY word, DATE(updated_at)
    ),
    latest_status AS (
        SELECT 
            word,
            successful_modes,
            row_number() OVER (PARTITION BY word ORDER BY attempt_date DESC) as rn
        FROM daily_attempts
    )
    SELECT word
    FROM latest_status
    WHERE rn = 1 AND successful_modes = 3;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_learned_words): {e}")
        return []

def get_mastered_words_with_recency(conn, user_id):
    """
    Returns mastered words with the timestamp of the latest mastered learning day
    (word + learned_at only). Uses the same 3-mode round-1 mastery rule as
    get_learned_words(). Kept lightweight — no vocabulary join — since callers only
    need the word and its recency; per-word details come from get_mastered_words_page().
    """
    if not conn:
        return []

    query = """
    WITH daily_attempts AS (
        SELECT
            word,
            DATE(updated_at) AS attempt_date,
            MAX(updated_at) AS learned_at,
            COUNT(DISTINCT CASE WHEN is_correct = true THEN mode END) AS successful_modes
        FROM vocab_records
        WHERE mode IN ('typing', 'listen', 'meaning')
          AND round_num = 1
          AND user_id = %s
        GROUP BY word, DATE(updated_at)
    ),
    latest_status AS (
        SELECT
            word,
            learned_at,
            successful_modes,
            ROW_NUMBER() OVER (PARTITION BY word ORDER BY attempt_date DESC) AS rn
        FROM daily_attempts
    )
    SELECT ls.word, ls.learned_at
    FROM latest_status ls
    WHERE ls.rn = 1 AND ls.successful_modes = 3;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            return [{"word": row[0], "learned_at": row[1]} for row in cur.fetchall()]
    except Exception as e:
        print(f"⚠️ Database query failed (get_mastered_words_with_recency): {e}")
        return []

def get_mastered_words_page(conn, user_id, page=1, page_size=24):
    """
    Returns one page of mastered words with the timestamp of the latest mastered learning day.
    Uses the same 3-mode round-1 mastery rule as get_learned_words().
    """
    page_size = min(100, max(1, int(page_size or 24)))
    page = max(1, int(page or 1))
    if not conn:
        return {"rows": [], "page": 1, "page_size": page_size, "total": 0, "total_pages": 1}

    base_cte = """
    WITH daily_attempts AS (
        SELECT
            word,
            DATE(updated_at) AS attempt_date,
            MAX(updated_at) AS learned_at,
            COUNT(DISTINCT CASE WHEN is_correct = true THEN mode END) AS successful_modes
        FROM vocab_records
        WHERE mode IN ('typing', 'listen', 'meaning')
          AND round_num = 1
          AND user_id = %s
        GROUP BY word, DATE(updated_at)
    ),
    latest_status AS (
        SELECT
            word,
            learned_at,
            successful_modes,
            ROW_NUMBER() OVER (PARTITION BY word ORDER BY attempt_date DESC) AS rn
        FROM daily_attempts
    ),
    mastered AS (
        SELECT word, learned_at
        FROM latest_status
        WHERE rn = 1 AND successful_modes = 3
    )
    """
    count_query = base_cte + """
    SELECT COUNT(*) FROM mastered;
    """
    rows_query = base_cte + """
    SELECT m.word, m.learned_at, v.pinyin, v.meaning_vn, v.meaning_en, v.audio_key, v.hsk_level
    FROM mastered m
    LEFT JOIN vocabulary v ON v.cn = m.word
    ORDER BY m.learned_at DESC NULLS LAST, m.word
    LIMIT %s OFFSET %s;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(count_query, (user_id,))
            total = int(cur.fetchone()[0] or 0)
            total_pages = max(1, (total + page_size - 1) // page_size)
            page = min(page, total_pages)
            offset = (page - 1) * page_size
            cur.execute(rows_query, (user_id, page_size, offset))
            rows = cur.fetchall()

        return {
            "rows": [
                {
                    "word": row[0],
                    "cn": row[0],
                    "learned_at": row[1].isoformat() if hasattr(row[1], "isoformat") else row[1],
                    "pinyin": row[2] or "",
                    "meaning_vn": row[3] or "",
                    "meaning_en": row[4] or "",
                    "audio_key": row[5] or "",
                    "hsk_level": row[6] or "",
                    "level": row[6] or "",
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    except Exception as e:
        print(f"⚠️ Database query failed (get_mastered_words_page): {e}")
        return {"rows": [], "page": 1, "page_size": page_size, "total": 0, "total_pages": 1}

def greedy_rank_recommendations(results):
    """
    Rank groups by recent mastered words while spreading matched-word coverage.
    """
    ranked = []
    remaining = list(results)
    covered_words = set()

    def stable_key(item):
        progress = str(item.get('progress') or '')
        return (
            item.get('level') or 0,
            item.get('lesson') or 0,
            item.get('category') or '',
            progress
        )

    remaining.sort(key=stable_key)

    while remaining:
        best_index = 0
        best_score = None
        for idx, item in enumerate(remaining):
            matched_words = set(item.get('matched_words') or [])
            new_words = matched_words - covered_words
            recent_new = set(item.get('recent_matched_words') or []) - covered_words
            newest_value = item.get('newest_learned_sort') or 0

            score = (
                len(recent_new),
                len(new_words),
                item.get('recent_score', 0),
                newest_value,
                item.get('coverage', 0),
                -len(matched_words)
            )
            if best_score is None or score > best_score:
                best_score = score
                best_index = idx

        selected = remaining.pop(best_index)
        ranked.append(selected)
        covered_words.update(selected.get('matched_words') or [])

    return ranked

# Recommendations only consider groups that contain at least one of the user's most
# recently mastered words. This keeps the coverage computation bounded (and fast) as a
# user's vocabulary grows, instead of scanning the whole question bank every call.
RECOMMEND_RECENT_WORD_LIMIT = 80

# Hard cap on how many ready groups we rank and return. Ranking is O(n²) and a power user
# can be "ready" for hundreds of groups — far more than anyone browses. We keep the groups
# most relevant to what they just learned, so the cap trims the long tail, not the top picks.
RECOMMEND_MAX_GROUPS = 60


def get_recommended_practices(conn, user_id, threshold=0.75, limit=None, status_filter=None):
    """
    Returns practice progress groups the user is ready for.
    Uses question_bank + learning_units + vocab_records — NO CSV loading.

    A group is recommended when coverage = known_words/total_words >= threshold.
    Excludes groups where the user's latest session was 100% correct.

    Returns list of dicts:
      {level, lesson, progress, skill, type, unit_ids,
       total_words, known_words, coverage, coverage_pct, questions: [...]}
    """
    if not conn:
        return []

    try:
        # 1. Get mastered words (3-mode logic) — word + learned_at only (no vocabulary join)
        mastered_rows = get_mastered_words_with_recency(conn, user_id)
        if not mastered_rows:
            return []
        mastered_recency = {row["word"]: row["learned_at"] for row in mastered_rows}
        mastered = list(mastered_recency.keys())
        sorted_mastered = sorted(
            mastered_rows,
            key=lambda row: row["learned_at"].timestamp() if row["learned_at"] else 0,
            reverse=True
        )
        recent_window_size = min(10, max(3, len(sorted_mastered) // 3 or 1))
        recent_words = {row["word"] for row in sorted_mastered[:recent_window_size]}

        # Recency-scoped candidate words: the most recently mastered words drive which
        # groups we bother scoring. Keeps the coverage query bounded as vocab grows.
        candidate_words = [row["word"] for row in sorted_mastered[:RECOMMEND_RECENT_WORD_LIMIT]]
        if not candidate_words:
            return []

        # Infer the learner's active HSK level(s) from the levels of their recent words.
        # Common words (你, 好, …) appear in practice groups at every level, so without this
        # a handful of recent words match thousands of units across the whole bank. We scope
        # candidate groups to these levels; if none can be resolved we fall back to no filter.
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT substring(hsk_level from '[0-9]+')::int AS lvl
                FROM vocabulary
                WHERE cn = ANY(%s) AND hsk_level ~ '[0-9]'
            """, (candidate_words,))
            active_levels = [r[0] for r in cur.fetchall() if r[0] and 1 <= r[0] <= 6]

        # 2a. Shortlist candidate groups: only those that contain a recent word AND sit at
        #     one of the learner's active levels, then take every unit in those groups
        #     (coverage still needs the full group word set).
        level_clause = "AND qb2.level = ANY(%s)" if active_levels else ""
        shortlist_params = [candidate_words]
        if active_levels:
            shortlist_params.append(active_levels)
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT DISTINCT qb.unit_id
                FROM question_bank qb
                WHERE qb.category IN ('practice', 'exam')
                  AND (qb.category, qb.level, qb.lesson, qb.progress) IN (
                        SELECT DISTINCT qb2.category, qb2.level, qb2.lesson, qb2.progress
                        FROM learning_units lu
                        JOIN question_bank qb2 ON lu.unit_id = qb2.unit_id
                        WHERE qb2.category IN ('practice', 'exam')
                          AND lu.unique_word = ANY(%s)
                          {level_clause}
                  )
            """, tuple(shortlist_params))
            candidate_unit_ids = [row[0] for row in cur.fetchall()]
        if not candidate_unit_ids:
            return []

        # 2b. Compute coverage only for those candidate units (bounded set).
        #     Dedupe each unit to its group first, then the (group, word) pairs, so the
        #     final aggregate is plain COUNT(*) over distinct words (hash-aggregatable) —
        #     avoids the disk-spilling sort that COUNT(DISTINCT)/ARRAY_AGG(DISTINCT) forces.
        #     matched_words is returned straight from SQL (only the user's mastered words).
        coverage_sql = """
            WITH unit_groups AS (
                SELECT DISTINCT unit_id, category, level, lesson, progress
                FROM question_bank
                WHERE category IN ('practice', 'exam')
                  AND unit_id = ANY(%s)
            ),
            group_words AS (
                SELECT DISTINCT ug.category, ug.level, ug.lesson, ug.progress, lu.unique_word
                FROM unit_groups ug
                JOIN learning_units lu ON lu.unit_id = ug.unit_id
            )
            SELECT
                category, level, lesson, progress,
                COUNT(*)                                                     AS total_words,
                COUNT(*) FILTER (WHERE unique_word = ANY(%s))                AS known_words,
                ARRAY_AGG(unique_word) FILTER (WHERE unique_word = ANY(%s))  AS matched_words
            FROM group_words
            GROUP BY category, level, lesson, progress
        """
        with conn.cursor() as cur:
            cur.execute(coverage_sql, (candidate_unit_ids, list(mastered), list(mastered)))
            group_coverage = {
                (row[0], row[1], row[2], row[3]): {
                    'total_words': row[4],
                    'known_words': row[5],
                    'coverage': row[5] / row[4],
                    'matched_words': row[6] or []
                }
                for row in cur.fetchall()
                if row[4] > 0
            }

        # 3. Filter groups meeting threshold
        ready_keys = {k for k, d in group_coverage.items() if d['coverage'] >= threshold}
        if not ready_keys:
            return []

        # 4. Find latest sessions to determine status per recommendation group.
        #    Bound the scan to the ready groups' lessons so we don't join the user's
        #    entire practice history on every call.
        ready_levels = list({k[1] for k in ready_keys})
        ready_lessons = list({str(k[2]) for k in ready_keys})
        with conn.cursor() as cur:
            cur.execute("""
                WITH session_results AS (
                    SELECT
                           COALESCE(pr.category, qb.category::text, 'practice') AS category,
                           pr.hsk_level,
                           pr.lesson,
                           qb.progress,
                           pr.session_id,
                           SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::float / COUNT(*) AS pct,
                           MAX(pr.created_at) AS session_end
                    FROM practice_record pr
                    LEFT JOIN question_bank qb
                      ON qb.level = pr.hsk_level
                     AND qb.lesson::text = pr.lesson::text
                     AND qb.no = pr.question_no
                     AND qb.category::text = COALESCE(pr.category, 'practice')
                    WHERE pr.user_id = %s
                      AND pr.hsk_level = ANY(%s)
                      AND pr.lesson = ANY(%s)
                    GROUP BY COALESCE(pr.category, qb.category::text, 'practice'),
                             pr.hsk_level, pr.lesson, qb.progress, pr.session_id
                ),
                latest AS (
                    SELECT category, hsk_level, lesson, progress, pct,
                           ROW_NUMBER() OVER (
                               PARTITION BY category, hsk_level, lesson, progress
                               ORDER BY session_end DESC
                           ) AS rn
                    FROM session_results
                )
                SELECT category, hsk_level, lesson, progress, pct
                FROM latest
                WHERE rn = 1
            """, (user_id, ready_levels, ready_lessons))
            lesson_status = {}
            for r in cur.fetchall():
                cat, lvl, les, prog, pct = r[0], r[1], r[2], r[3], r[4]
                key = (cat, lvl, int(les) if str(les).isdigit() else les, prog)
                if pct == 1.0:
                    lesson_status[key] = "Finish and success"
                else:
                    lesson_status[key] = "Finish and fail"

        # 5. Build lightweight summaries before fetching question payloads.
        summaries = []
        for category, level, lesson, progress in ready_keys:
            status = lesson_status.get((category, level, lesson, progress), "Not start")
            if status_filter and status != status_filter:
                continue
            total = group_coverage[(category, level, lesson, progress)]['total_words']
            known = group_coverage[(category, level, lesson, progress)]['known_words']
            coverage = group_coverage[(category, level, lesson, progress)]['coverage']
            matched_words = sorted(group_coverage[(category, level, lesson, progress)]['matched_words'])
            recent_matched_words = sorted(
                [word for word in matched_words if word in recent_words],
                key=lambda word: mastered_recency.get(word) or 0,
                reverse=True
            )
            newest_learned_at = max(
                (mastered_recency.get(word) for word in matched_words if mastered_recency.get(word)),
                default=None
            )
            recent_score = sum(1 for word in matched_words if word in recent_words)
            
            summaries.append({
                'level':        level,
                'lesson':       lesson,
                'progress':     progress,
                'category':     category,
                'status':       status,
                'total_words':  total,
                'known_words':  known,
                'coverage':     round(coverage, 4),
                'coverage_pct': round(coverage * 100, 1),
                'matched_words': matched_words,
                'recent_matched_words': recent_matched_words,
                'newest_learned_at': newest_learned_at.isoformat() if newest_learned_at else None,
                'newest_learned_sort': newest_learned_at.timestamp() if newest_learned_at else 0,
                'recent_score': recent_score,
            })

        # Trim to the most relevant groups before the O(n²) greedy ranking: prioritise
        # groups tied to the most recently learned words, then newest match, then coverage.
        if len(summaries) > RECOMMEND_MAX_GROUPS:
            summaries.sort(
                key=lambda s: (s['recent_score'], s['newest_learned_sort'], s['coverage']),
                reverse=True
            )
            summaries = summaries[:RECOMMEND_MAX_GROUPS]

        ranked_summaries = greedy_rank_recommendations(summaries)
        if limit:
            ranked_summaries = ranked_summaries[:limit]
        if not ranked_summaries:
            return []

        # Fetch only lightweight per-group metadata (count + representative skill/type +
        # unit ids). The full question payloads aren't needed here — the practice screen
        # loads them on demand — so we avoid pulling every question's TEXT/JSONB columns.
        where_clauses = []
        params = []
        for item in ranked_summaries:
            where_clauses.append("(category = %s AND level = %s AND lesson = %s AND progress = %s)")
            params.extend([item['category'], item['level'], item['lesson'], item['progress']])

        meta_sql = f"""
            SELECT category, level, lesson, progress,
                   COUNT(*)                                AS question_count,
                   MODE() WITHIN GROUP (ORDER BY skill)    AS skill,
                   MIN(type)                               AS type,
                   ARRAY_AGG(DISTINCT unit_id)             AS unit_ids
            FROM question_bank
            WHERE {' OR '.join(where_clauses)}
            GROUP BY category, level, lesson, progress
        """
        with conn.cursor() as cur:
            cur.execute(meta_sql, params)
            meta_by_key = {
                (r[0], r[1], r[2], r[3]): {
                    'question_count': r[4],
                    'skill':          r[5] or 'listening',
                    'type':           r[6],
                    'unit_ids':       sorted(r[7] or []),
                }
                for r in cur.fetchall()
            }

        results = []
        for item in ranked_summaries:
            key = (item['category'], item['level'], item['lesson'], item['progress'])
            meta = meta_by_key.get(key)
            if not meta or not meta['question_count']:
                continue
            item['skill'] = meta['skill']
            item['type'] = meta['type']
            item['unit_ids'] = meta['unit_ids']
            item['question_count'] = meta['question_count']
            item.pop('newest_learned_sort', None)
            results.append(item)

        return results

    except Exception as e:
        print(f"[WARN] get_recommended_practices failed: {e}")
        return []


def get_practice_history_sessions(conn, user_id, hsk_level=None, category=None,
                                  sort='recent', page=1, page_size=20):
    """
    List a user's past practice/exam sessions for the review page, with optional
    backend filters (hsk_level, category) and ordering. One row per session_id, with
    score and the level(s)/lesson(s) it covered.

    Returns (sessions, has_more). has_more lets the caller do prev/next paging without a
    separate COUNT query (we fetch one extra row and trim it). Scoped to user_id.
    """
    if not conn:
        return [], False

    page = max(1, int(page or 1))
    page_size = min(50, max(1, int(page_size or 20)))
    order = "ASC" if sort == 'oldest' else "DESC"

    where = ["user_id = %s"]
    params = [user_id]
    if category in ('practice', 'exam'):
        where.append("COALESCE(category, 'practice') = %s")
        params.append(category)

    # Level can vary within a multi-lesson session, so keep the whole session (with its
    # full score) as long as it touched the requested level, rather than filtering rows.
    having = ""
    if hsk_level is not None:
        having = "HAVING bool_or(hsk_level = %s)"
        params.append(hsk_level)

    params.append(page_size + 1)          # fetch one extra to detect a next page
    params.append((page - 1) * page_size)

    sql = f"""
        SELECT session_id,
               MAX(created_at)                                   AS ended_at,
               COUNT(*)                                          AS total,
               SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)       AS correct,
               ARRAY_AGG(DISTINCT hsk_level)                     AS levels,
               ARRAY_AGG(DISTINCT lesson)                        AS lessons,
               ARRAY_AGG(DISTINCT COALESCE(category, 'practice')) AS categories
        FROM practice_record
        WHERE {' AND '.join(where)}
        GROUP BY session_id
        {having}
        ORDER BY ended_at {order}
        LIMIT %s OFFSET %s
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        sessions = []
        for row in rows:
            session_id, ended_at, total, correct, levels, lessons, categories = row
            total = total or 0
            correct = correct or 0
            sessions.append({
                'session_id':   session_id,
                'ended_at':     ended_at.isoformat() if ended_at else None,
                'total':        total,
                'correct':      correct,
                'score_pct':    round(correct / total * 100, 1) if total else 0.0,
                'levels':       sorted([l for l in (levels or []) if l is not None]),
                'lessons':      sorted([str(l) for l in (lessons or []) if l is not None]),
                'categories':   [c for c in (categories or []) if c],
            })
        return sessions, has_more
    except Exception as e:
        print(f"[WARN] get_practice_history_sessions failed: {e}")
        return [], False


def get_practice_session_detail(conn, user_id, session_id):
    """
    Full detail for one of the user's sessions: every answered question joined back
    to question_bank so the review page can show the prompt, options, correct answer
    and the user's own answer. Scoped to user_id so users only see their own records.
    """
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pr.hsk_level, pr.lesson, pr.question_no, pr.skill,
                       pr.question_type, pr.user_answer, pr.is_correct, pr.created_at,
                       COALESCE(pr.category, 'practice')                AS category,
                       qb.content, qb.question, qb.answer, qb.audio_key,
                       qb.image, qb.options, qb.progress
                FROM practice_record pr
                LEFT JOIN question_bank qb
                  ON qb.level = pr.hsk_level
                 AND qb.lesson::text = pr.lesson::text
                 AND qb.no = pr.question_no
                 AND qb.category::text = COALESCE(pr.category, 'practice')
                WHERE pr.user_id = %s AND pr.session_id = %s
                ORDER BY pr.hsk_level, pr.lesson, qb.progress, pr.question_no, pr.created_at
            """, (user_id, session_id))
            cols = ['level', 'lesson', 'no', 'skill', 'type', 'user_answer',
                    'is_correct', 'answered_at', 'category', 'content', 'question',
                    'answer', 'audio_key', 'image', 'options', 'progress']
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return rows
    except Exception as e:
        print(f"[WARN] get_practice_session_detail failed: {e}")
        return None


def get_unlearned_words_from_db(conn, user_id):

    """
    Returns a list of words from the user's history that have NOT been fully learned 
    (less than 3 distinct correct modes in round 1).
    """
    if not conn:
        return []

    query = """
with daily_attempts as (
    -- Group attempts by word and date
    select 
        word, 
        DATE(updated_at) as attempt_date,
        count(distinct case when is_correct = true then mode end) as successful_modes
    from vocab_records
    where mode in ('typing', 'listen', 'meaning')
      and round_num = 1
      and user_id = %s
    group by word, DATE(updated_at)
),
latest_status as (
    -- Get the most recent day's result for each word
    select 
        word,
        successful_modes,
        row_number() over (partition by word order by attempt_date desc) as rn
    from daily_attempts
)
-- Select words that haven't mastered all 3 modes on their most recent practice day
select word
from latest_status
where rn = 1 and successful_modes < 3
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_unlearned_words_from_db): {e}")
        return []

def get_unsure_words_from_db(conn, user_id):
    """
    Returns a list of unsure words that the given user has learned but takes a longer time to answer.
    """
    if not conn:
        return []

    query = """
    WITH learned_words AS (
        SELECT word
        FROM vocab_records 
        WHERE is_correct = true
          AND user_id = %s
        GROUP BY word
        HAVING COUNT(*) >= 3
    ),
    stats AS (
        SELECT a.mode,
               AVG(a.response_time_ms) AS avg_rt,
               NULLIF(STDDEV(a.response_time_ms), 0) AS std_rt
        FROM vocab_records a
        JOIN learned_words b ON a.word = b.word
        WHERE a.user_id = %s
        GROUP BY a.mode
    )
    SELECT a.word
    FROM vocab_records a
    JOIN learned_words b ON a.word = b.word
    JOIN stats s ON a.mode = s.mode
    WHERE a.user_id = %s
      AND s.std_rt IS NOT NULL AND (a.response_time_ms - s.avg_rt) / s.std_rt > 1.0
    GROUP BY a.word
    ORDER BY MAX((a.response_time_ms - s.avg_rt) / s.std_rt) DESC;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, user_id, user_id))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_unsure_words_from_db): {e}")
        return []

def get_hard_semantic_learned_words(conn, user_id):
    """
    Returns a list of learned words (by the given user) but difficult in semantic.
    """
    if not conn:
        return []

    query = """
    WITH learned_words AS (
        SELECT word
        FROM vocab_records 
        WHERE is_correct IS TRUE
          AND user_id = %s
        GROUP BY word
        HAVING COUNT(*) >= 3
    )
    SELECT a.word, b.id AS word_id, c.strokes_difficult_cn, d.sematic_difficulty
    FROM learned_words a
    LEFT JOIN chinese_dict b ON a.word = b.cn
    LEFT JOIN chinese_stroke_info c ON a.word = c.cn
    LEFT JOIN sematic_diffculty d ON b.id = d.word_id
    ORDER BY d.sematic_difficulty DESC NULLS LAST;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_semantic_learned_words): {e}")
        return []

def get_hard_stroke_learned_words(conn, user_id):
    """
    Returns a list of learned words (by the given user) but difficult in strokes.
    """
    if not conn:
        return []

    query = """
    WITH learned_words AS (
        SELECT word
        FROM vocab_records 
        WHERE is_correct IS TRUE
          AND user_id = %s
        GROUP BY word
        HAVING COUNT(*) >= 3
    )
    SELECT a.word, b.id AS word_id, c.strokes_difficult_cn, d.sematic_difficulty, 
           (c.strokes_difficult_cn * d.sematic_difficulty) AS total_difficulty
    FROM learned_words a
    LEFT JOIN chinese_dict b ON a.word = b.cn
    LEFT JOIN chinese_stroke_info c ON a.word = c.cn
    LEFT JOIN sematic_diffculty d ON b.id = d.word_id
    ORDER BY c.strokes_difficult_cn DESC NULLS LAST;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_stroke_learned_words): {e}")
        return []

def get_passages_summary(conn, hsk_level=None):
    if not conn: return []
    query = """
        SELECT p.passage_id, p.hsk_level, count(l.id) as line_count 
        FROM lesson_passages p
        LEFT JOIN lesson_lines l ON p.passage_id = l.passage_id
    """
    params = ()
    if hsk_level:
        query += " WHERE p.hsk_level = %s"
        params = (hsk_level,)
    query += " GROUP BY p.passage_id, p.hsk_level ORDER BY p.passage_id"
    
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [{"passage_id": r[0], "hsk_level": r[1], "line_count": r[2]} for r in rows]

def get_passage_content(conn, passage_id):
    if not conn: return None
    with conn.cursor() as cur:
        cur.execute("SELECT hsk_level FROM lesson_passages WHERE passage_id = %s", (passage_id,))
        row = cur.fetchone()
        if not row:
            return None
        hsk_level = row[0]
        
        cur.execute("""
            SELECT line_id, speaker, content, pinyin, audio_key, translation_en, translation_vi, tokens
            FROM lesson_lines
            WHERE passage_id = %s
            ORDER BY line_id
        """, (passage_id,))
        lines = []
        for r in cur.fetchall():
            lines.append({
                "line_id": r[0],
                "speaker": r[1],
                "content": r[2],
                "pinyin": r[3],
                "audio_key": r[4],
                "translations": {
                    "en": r[5],
                    "vi": r[6]
                },
                "tokens": r[7] if r[7] else []
            })
            
        return {
            "passage_id": passage_id,
            "hsk_level": hsk_level,
            "lines": lines
        }

def get_course_vocab(conn):
    import pandas as pd
    if not conn: return pd.DataFrame()
    with conn.cursor() as cur:
        cur.execute("SELECT cn as word, pinyin, meaning_vn, meaning_en, audio_key, hsk_level as level FROM vocabulary ORDER BY hsk_level, id")
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=['word', 'pinyin', 'meaning_vn', 'meaning_en', 'audio_key', 'level'])
        return df

def has_vocab_history(conn, user_id):
    """Returns True if the user has any vocab_records entries."""
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM vocab_records WHERE user_id = %s LIMIT 1", (user_id,))
            return cur.fetchone() is not None
    except Exception as e:
        print(f"⚠️ Database query failed (has_vocab_history): {e}")
        return False

def get_vocab_lessons(conn, hsk_level, lesson_size=10):
    """
    Returns a list of lesson groups for a given HSK level.
    Each lesson contains lesson_size words.
    Returns: [{lesson: 1, start_idx: 0, end_idx: 9, word_count: 10, preview: ['你','好',...]}, ...]
    """
    import pandas as pd
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cn FROM vocabulary WHERE hsk_level = %s ORDER BY id",
                (hsk_level,)
            )
            rows = cur.fetchall()
        words = [r[0] for r in rows]
        lessons = []
        for i in range(0, len(words), lesson_size):
            chunk = words[i:i + lesson_size]
            lessons.append({
                "lesson": (i // lesson_size) + 1,
                "start_idx": i,
                "end_idx": i + len(chunk) - 1,
                "word_count": len(chunk),
                "preview": chunk[:4]  # first 4 words as preview
            })
        return lessons
    except Exception as e:
        print(f"⚠️ Database query failed (get_vocab_lessons): {e}")
        return []

def get_all_vn_meanings(conn):
    if not conn: return []
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT meaning_vn FROM vocabulary WHERE meaning_vn IS NOT NULL AND meaning_vn != ''")
        rows = cur.fetchall()
        return [r[0] for r in rows]

def get_passage_vocab(conn, passage_id):
    """Return vocabulary words linked to a passage via passage_vocabulary."""
    if not conn: return []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT v.cn, v.pinyin, v.meaning_vn, v.meaning_en, v.audio_key, v.hsk_level
            FROM passage_vocabulary pv
            JOIN vocabulary v ON v.cn = pv.cn
            WHERE pv.passage_id = %s
            ORDER BY v.cn
        """, (passage_id,))
        rows = cur.fetchall()
        return [
            {
                "cn":          r[0],
                "pinyin":      r[1] or "",
                "meaning_vn":  r[2] or "",
                "meaning_en":  r[3] or "",
                "audio_key":   r[4] or "",
                "hsk_level":   r[5] or ""
            }
            for r in rows
        ]

def get_grammar_for_passage(conn, hsk_level, lesson, passage_number):
    try:
        prefix = f'H{hsk_level}-{lesson}-%'
        with conn.cursor() as cur:
            cur.execute('''
                SELECT r.grammar_id, r.type, r.vietnamese_content, r.english_content, 
                       c_vn.content_json AS vn_context,
                       c_en.content_json AS en_context
                FROM grammar_rule r
                LEFT JOIN grammar_context c_vn ON r.vietnamese_content = c_vn.grammar_id AND r.type = 4
                LEFT JOIN grammar_context c_en ON r.english_content = c_en.grammar_id AND r.type = 4
                WHERE r.grammar_id LIKE %s AND r.passage_number = %s
                ORDER BY r.id ASC
            ''', (prefix, passage_number))
            cols = ['grammar_id', 'type', 'vietnamese_content', 'english_content', 'vn_context', 'en_context']
            results = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if d.get('vn_context') is None:
                    d.pop('vn_context', None)
                if d.get('en_context') is None:
                    d.pop('en_context', None)
                results.append(d)
            return results
    except Exception as e:
        print(f'[WARN] get_grammar_for_passage failed: {e}')
        return []
