"""
db/competition.py
------------------
Queries for the multiplayer "Learn Together" feature — competition rooms,
sessions, sections, questions, answers, scores and chat.
Extracted from the former monolithic db.py.
"""

import json

from sqlalchemy import select, update, func, case, and_, literal, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert

from entity.database import SessionLocal
from entity.user.entity import User
from entity.competition.entity import (
    CompetitionRoom,
    CompetitionRoomMember,
    CompetitionChatMessage,
    CompetitionSession,
    CompetitionScore,
    CompetitionVocabAnswer,
)


# A room is either a vocabulary competition or the lesson trainer; vocab rooms also
# pick a skill focus ('all' = all-rounder, or a single activity).
ROOM_CATEGORIES = ("vocab", "lesson")
VOCAB_ACTIVITY_TYPES = ("all", "typing", "listening", "reading")


def prepare_room_settings(data):
    """Normalize + validate the room settings shared by room creation and host edits.
    Returns (settings, error): settings carries level, passage_ids, category,
    activity_type, max_users, section_timeout_minutes and source_count (vocab words or
    lesson lines). error is a user-facing string when the input is unusable."""
    data = data or {}
    try:
        level = int(data.get("level"))
    except (TypeError, ValueError):
        return None, "HSK level is required"

    passage_ids = [str(p).strip() for p in (data.get("passage_ids") or []) if str(p).strip()]
    if not passage_ids:
        return None, "Select at least one lesson part"

    category = str(data.get("category") or "vocab").strip().lower()
    if category not in ROOM_CATEGORIES:
        category = "vocab"

    activity_type = str(data.get("activity_type") or "all").strip().lower()
    if category != "vocab" or activity_type not in VOCAB_ACTIVITY_TYPES:
        # Only the vocab competition has a skill focus; lessons always run the full mix.
        activity_type = "all"

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

    # source_count doubles as the room's "material" count: vocab words, or lesson lines.
    if category == "lesson":
        from service.lesson_task_service import count_lesson_lines
        source_count = count_lesson_lines(passage_ids)
        if not source_count:
            return None, "The selected lessons have no tasks"
    else:
        words = resolve_room_words(passage_ids)
        if not words:
            return None, "The selected parts have no vocabulary"
        source_count = len(words)

    return {
        "level": level,
        "passage_ids": passage_ids,
        "category": category,
        "activity_type": activity_type,
        "max_users": max_users,
        "section_timeout_minutes": section_timeout_minutes,
        "source_count": source_count,
    }, None


def resolve_room_words(passage_ids):
    """Union the vocabulary of the selected passages into a deduped word list
    (rows as returned by get_passage_vocab, keyed by 'cn'). Shared by room
    creation (word count) and answer validation."""
    from db.content import get_passage_vocab
    if not passage_ids:
        return []
    collected = []
    seen = set()
    for pid in passage_ids:
        for row in get_passage_vocab(pid):
            cn = row.get("cn")
            if cn and cn not in seen:
                seen.add(cn)
                collected.append(row)
    return collected

def create_competition_room(room_code, host_user_id, level, passage_ids, word_count,
                            max_users, section_timeout_minutes,
                            category="vocab", activity_type="all"):
    session = SessionLocal()
    try:
        room_id = session.execute(
            pg_insert(CompetitionRoom)
            .values(
                room_code=room_code, host_user_id=host_user_id, category=category,
                activity_type=activity_type,
                level=level, passage_ids=list(passage_ids), word_count=word_count,
                max_users=max_users, section_timeout_minutes=section_timeout_minutes,
                status="waiting",
            )
            .returning(CompetitionRoom.id)
        ).scalar_one()
        session.execute(
            pg_insert(CompetitionRoomMember)
            .values(room_id=room_id, user_id=host_user_id, role="host", status="online")
            .on_conflict_do_update(
                index_elements=["room_id", "user_id"],
                set_={
                    "role": "host", "status": "online",
                    "left_at": None, "last_seen_at": func.now(),
                },
            )
        )
        session.commit()
        return get_competition_room_by_code(room_code)
    except Exception as e:
        print(f"Database create_competition_room failed: {e}")
        session.rollback()
        return None
    finally:
        SessionLocal.remove()

def get_competition_room_by_code(room_code):
    if not room_code:
        return None
    session = SessionLocal()
    try:
        r = CompetitionRoom
        row = session.execute(
            select(
                r.id, r.room_code, r.host_user_id, r.level, r.passage_ids, r.word_count,
                r.max_users, r.section_timeout_minutes, r.status, r.created_at, r.updated_at,
                r.category, r.activity_type,
            )
            .where(r.room_code == str(room_code).upper())
        ).first()
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
            "category": row[11] or "vocab",
            "activity_type": row[12] or "all",
        }
    except Exception as e:
        print(f"Database get_competition_room_by_code failed: {e}")
        return None
    finally:
        SessionLocal.remove()

def join_competition_room(room_code, user_id):
    room = get_competition_room_by_code(room_code)
    if not room:
        return None, "Room not found"
    session = SessionLocal()
    try:
        m = CompetitionRoomMember
        active_count = int(session.execute(
            select(func.count()).select_from(m)
            .where(m.room_id == room["id"], m.status != "left")
        ).scalar() or 0)
        already_member = session.execute(
            select(m.id).where(m.room_id == room["id"], m.user_id == user_id)
        ).first() is not None
        if not already_member and active_count >= int(room["max_users"] or 8):
            return None, "Room is full"

        role = 'host' if int(room["host_user_id"]) == int(user_id) else 'participant'
        session.execute(
            pg_insert(m)
            .values(room_id=room["id"], user_id=user_id, role=role, status="online")
            .on_conflict_do_update(
                index_elements=["room_id", "user_id"],
                set_={"status": "online", "left_at": None, "last_seen_at": func.now()},
            )
        )
        session.commit()
        return get_competition_room_state(room_code), None
    except Exception as e:
        print(f"Database join_competition_room failed: {e}")
        session.rollback()
        return None, "Could not join room"
    finally:
        SessionLocal.remove()

def leave_competition_room(room_code, user_id):
    room = get_competition_room_by_code(room_code)
    if not room:
        return False
    session = SessionLocal()
    try:
        m = CompetitionRoomMember
        session.execute(
            update(m)
            .where(m.room_id == room["id"], m.user_id == user_id)
            .values(status="left", left_at=func.now(), last_seen_at=func.now())
        )
        session.commit()
        return True
    except Exception as e:
        print(f"Database leave_competition_room failed: {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()

def get_competition_room_state(room_code):
    room = get_competition_room_by_code(room_code)
    if not room:
        return None
    session = SessionLocal()
    try:
        m = CompetitionRoomMember
        members = [
            {
                "user_id": row[0],
                "username": row[1],
                "role": row[2],
                "status": row[3],
                "joined_at": row[4].isoformat() if row[4] else None,
            }
            for row in session.execute(
                select(m.user_id, User.username, m.role, m.status, m.joined_at)
                .select_from(m).join(User, User.id == m.user_id)
                .where(m.room_id == room["id"], m.status != "left")
                .order_by(case((m.role == "host", 0), else_=1), m.joined_at)
            ).all()
        ]

        c = CompetitionChatMessage
        chat = [
            {
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "message": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }
            for row in reversed(session.execute(
                select(c.id, c.user_id, User.username, c.message, c.created_at)
                .select_from(c).join(User, User.id == c.user_id)
                .where(c.room_id == room["id"])
                .order_by(c.created_at.desc())
                .limit(50)
            ).all())
        ]

        s = CompetitionSession
        session_row = session.execute(
            select(s.id, s.status, s.current_section, s.section_started_at,
                   s.section_ends_at, s.started_at, s.finished_at)
            .where(s.room_id == room["id"])
            .order_by(s.id.desc())
            .limit(1)
        ).first()
        session_state = None
        if session_row:
            session_state = {
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
        room["session"] = session_state
        return room
    except Exception as e:
        print(f"Database get_competition_room_state failed: {e}")
        return None
    finally:
        SessionLocal.remove()

def update_competition_room(room_code, host_user_id, data):
    """Host edit of an existing room's settings while it is waiting. Validates the new
    settings, applies them and returns the fresh room state so it can be re-broadcast."""
    room = get_competition_room_by_code(room_code)
    if not room:
        return None, "Room not found"
    if int(room["host_user_id"]) != int(host_user_id):
        return None, "Only the host can edit the room"
    if room["status"] == "running":
        return None, "Cannot edit while the round is running"

    settings, error = prepare_room_settings(data)
    if error:
        return None, error

    session = SessionLocal()
    try:
        session.execute(
            update(CompetitionRoom)
            .where(CompetitionRoom.id == room["id"])
            .values(
                category=settings["category"], activity_type=settings["activity_type"],
                level=settings["level"], passage_ids=list(settings["passage_ids"]),
                word_count=settings["source_count"], max_users=settings["max_users"],
                section_timeout_minutes=settings["section_timeout_minutes"],
                updated_at=func.now(),
            )
        )
        session.commit()
        return get_competition_room_state(room_code), None
    except Exception as e:
        print(f"Database update_competition_room failed: {e}")
        session.rollback()
        return None, "Could not update room"
    finally:
        SessionLocal.remove()

def add_competition_chat_message(room_code, user_id, message):
    room = get_competition_room_by_code(room_code)
    text = str(message or "").strip()[:1000]
    if not room or not text:
        return None
    session = SessionLocal()
    try:
        c = CompetitionChatMessage
        row = session.execute(
            pg_insert(c)
            .values(room_id=room["id"], user_id=user_id, message=text)
            .returning(c.id, c.created_at)
        ).first()
        user_row = session.execute(
            select(User.username).where(User.id == user_id)
        ).first()
        session.commit()
        return {
            "id": row[0],
            "user_id": user_id,
            "username": user_row[0] if user_row else "User",
            "message": text,
            "created_at": row[1].isoformat() if row[1] else None,
        }
    except Exception as e:
        print(f"Database add_competition_chat_message failed: {e}")
        session.rollback()
        return None
    finally:
        SessionLocal.remove()

def start_competition_session(room_code, host_user_id):
    room = get_competition_room_by_code(room_code)
    if not room:
        return None, "Room not found"
    if int(room["host_user_id"]) != int(host_user_id):
        return None, "Only the host can start"
    if room["status"] == "running":
        return None, "Room is already running"
    if not room.get("passage_ids"):
        return None, "No lessons selected"

    category = room.get("category") or "vocab"
    # Lesson rooms generate one shared task set now, so every participant answers the
    # same questions; vocab rooms resolve their word list on the client instead.
    lesson_tasks = None
    if category == "lesson":
        from service.lesson_task_service import build_lesson_tasks
        lesson_tasks = build_lesson_tasks(room["passage_ids"], mode="master")
        if not lesson_tasks:
            return None, "The selected lessons have no tasks"

    session = SessionLocal()
    try:
        session.execute(
            update(CompetitionRoom)
            .where(CompetitionRoom.id == room["id"])
            .values(status="running", updated_at=func.now())
        )
        minutes = int(room["section_timeout_minutes"] or 15)
        session_id = session.execute(
            pg_insert(CompetitionSession)
            .values(
                room_id=room["id"], status="running", current_section=category,
                section_started_at=func.now(),
                section_ends_at=func.now() + literal_column("interval '1 minute'") * minutes,
                started_at=func.now(), lesson_tasks=lesson_tasks,
            )
            .returning(CompetitionSession.id)
        ).scalar_one()

        session.execute(
            pg_insert(CompetitionScore)
            .from_select(
                ["session_id", "user_id"],
                select(literal(session_id), CompetitionRoomMember.user_id)
                .where(
                    CompetitionRoomMember.room_id == room["id"],
                    CompetitionRoomMember.status != "left",
                ),
            )
            .on_conflict_do_nothing(index_elements=["session_id", "user_id"])
        )
        session.commit()
        return get_competition_session_state(session_id), None
    except Exception as e:
        print(f"Database start_competition_session failed: {e}")
        session.rollback()
        return None, "Could not start session"
    finally:
        SessionLocal.remove()

def get_active_competition_session(room_code):
    room = get_competition_room_by_code(room_code)
    if not room:
        return None
    session = SessionLocal()
    try:
        row = session.execute(
            select(CompetitionSession.id)
            .where(CompetitionSession.room_id == room["id"])
            .order_by(CompetitionSession.id.desc())
            .limit(1)
        ).first()
        return get_competition_session_state(row[0]) if row else None
    except Exception as e:
        print(f"Database get_active_competition_session failed: {e}")
        return None
    finally:
        SessionLocal.remove()

def get_competition_session_state(session_id):
    if not session_id:
        return None
    session = SessionLocal()
    try:
        s = CompetitionSession
        r = CompetitionRoom
        row = session.execute(
            select(
                s.id, s.room_id, r.room_code, s.status, s.current_section,
                s.section_started_at, s.section_ends_at, s.started_at, s.finished_at,
                r.category, r.activity_type, s.lesson_tasks,
            )
            .select_from(s).join(r, r.id == s.room_id)
            .where(s.id == session_id)
        ).first()
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
            "category": row[9] or "vocab",
            "activity_type": row[10] or "all",
            "lesson_tasks": row[11] or [],
        }
        state["scores"] = get_competition_scores(session_id)
        return state
    except Exception as e:
        print(f"Database get_competition_session_state failed: {e}")
        return None
    finally:
        SessionLocal.remove()

# Per-mode scoring: base points + a time-decay speed bonus, minus a per-error penalty
# on the matching modes. Time uses fractional seconds; typing is binary (an incorrect
# submission scores nothing). See the scoring spec for the rationale behind each value.
MODE_CONFIG = {
    "typing":  {"base": 120, "max_bonus": 60, "decay": 5.0, "penalty_rate": 0.0},
    "listen":  {"base": 100, "max_bonus": 50, "decay": 2.0, "penalty_rate": 0.10},
    "meaning": {"base": 80,  "max_bonus": 40, "decay": 3.0, "penalty_rate": 0.10},
    # Lesson-mode task types. The lesson trainer is one-shot per task (no wrong-attempt
    # tracking), so these carry no error penalty; a wrong answer simply scores nothing.
    "listening": {"base": 100, "max_bonus": 50, "decay": 2.0, "penalty_rate": 0.0},
    "reorder":   {"base": 130, "max_bonus": 60, "decay": 4.0, "penalty_rate": 0.0},
}

# The task types the lesson trainer produces (see service/lesson_task_service.py).
LESSON_ACTIVITY_TYPES = ("listening", "meaning", "typing", "reorder")

def calculate_competition_points(activity_type, is_correct, response_time_ms, wrong_attempts=0):
    cfg = MODE_CONFIG.get(activity_type)
    if not cfg:
        return 0
    # An incorrect or skipped answer never scores, in any mode.
    if not is_correct:
        return 0
    seconds = max(0.0, int(response_time_ms or 0) / 1000.0)
    penalty = max(0, int(wrong_attempts or 0)) * (cfg["base"] * cfg["penalty_rate"])
    bonus = max(0.0, cfg["max_bonus"] - (seconds * cfg["decay"]))
    return max(0, round((cfg["base"] - penalty) + bonus))

def record_competition_vocab_answer(session_id, user_id, word, activity_type, is_correct, response_time_ms, wrong_attempts=0):
    """Record one participant's answer for a word/activity, awarding points per the
    per-mode scoring rules (speed bonus, minus per-error penalties on the matching
    modes). One-shot per (word, activity_type); the client reports correctness, timing
    and wrong-attempt count, matching the solo trainer's trust model."""
    word = str(word or "").strip()
    activity_type = str(activity_type or "").strip()
    if not word or activity_type not in ("typing", "listen", "meaning"):
        return None, "Invalid answer payload"
    session = SessionLocal()
    try:
        # Only accept answers while the session is running and the user is a scored participant.
        active = session.execute(
            select(literal(1))
            .select_from(CompetitionSession)
            .join(
                CompetitionScore,
                and_(
                    CompetitionScore.session_id == CompetitionSession.id,
                    CompetitionScore.user_id == user_id,
                ),
            )
            .where(CompetitionSession.id == session_id, CompetitionSession.status == "running")
        ).first()
        if not active:
            return None, "Session is not active"

        is_correct = bool(is_correct)
        points = calculate_competition_points(activity_type, is_correct, response_time_ms, wrong_attempts)
        inserted = session.execute(
            pg_insert(CompetitionVocabAnswer)
            .values(
                session_id=session_id, user_id=user_id, word=word,
                activity_type=activity_type, is_correct=is_correct,
                response_time_ms=int(response_time_ms or 0), points=points,
            )
            .on_conflict_do_nothing(
                index_elements=["session_id", "user_id", "word", "activity_type"]
            )
            .returning(CompetitionVocabAnswer.id)
        ).first()
        if not inserted:
            return None, "Answer already submitted"
        session.execute(
            update(CompetitionScore)
            .where(
                CompetitionScore.session_id == session_id,
                CompetitionScore.user_id == user_id,
            )
            .values(
                total_points=CompetitionScore.total_points + points,
                total_response_time_ms=CompetitionScore.total_response_time_ms + int(response_time_ms or 0),
                updated_at=func.now(),
            )
        )
        session.commit()
        return {
            "is_correct": is_correct,
            "points": points,
            "scores": get_competition_scores(session_id),
        }, None
    except Exception as e:
        print(f"Database record_competition_vocab_answer failed: {e}")
        session.rollback()
        return None, "Could not record answer"
    finally:
        SessionLocal.remove()

def record_competition_lesson_answer(session_id, user_id, item_key, task_type, is_correct, response_time_ms, wrong_attempts=0):
    """Record one participant's answer for a lesson task, awarding points per the
    per-mode scoring rules. `item_key` is the task's stable identity ("<passage>:<line>"),
    so each task scores once per participant. Reuses competition_vocab_answers — a
    session is either vocab or lesson, so the (word, activity_type) key never collides."""
    item_key = str(item_key or "").strip()
    task_type = str(task_type or "").strip()
    if not item_key or task_type not in LESSON_ACTIVITY_TYPES:
        return None, "Invalid answer payload"
    session = SessionLocal()
    try:
        # Only accept answers while the session is running and the user is a scored participant.
        active = session.execute(
            select(literal(1))
            .select_from(CompetitionSession)
            .join(
                CompetitionScore,
                and_(
                    CompetitionScore.session_id == CompetitionSession.id,
                    CompetitionScore.user_id == user_id,
                ),
            )
            .where(CompetitionSession.id == session_id, CompetitionSession.status == "running")
        ).first()
        if not active:
            return None, "Session is not active"

        is_correct = bool(is_correct)
        points = calculate_competition_points(task_type, is_correct, response_time_ms, wrong_attempts)
        inserted = session.execute(
            pg_insert(CompetitionVocabAnswer)
            .values(
                session_id=session_id, user_id=user_id, word=item_key,
                activity_type=task_type, is_correct=is_correct,
                response_time_ms=int(response_time_ms or 0), points=points,
            )
            .on_conflict_do_nothing(
                index_elements=["session_id", "user_id", "word", "activity_type"]
            )
            .returning(CompetitionVocabAnswer.id)
        ).first()
        if not inserted:
            return None, "Answer already submitted"
        session.execute(
            update(CompetitionScore)
            .where(
                CompetitionScore.session_id == session_id,
                CompetitionScore.user_id == user_id,
            )
            .values(
                total_points=CompetitionScore.total_points + points,
                total_response_time_ms=CompetitionScore.total_response_time_ms + int(response_time_ms or 0),
                updated_at=func.now(),
            )
        )
        session.commit()
        return {
            "is_correct": is_correct,
            "points": points,
            "scores": get_competition_scores(session_id),
        }, None
    except Exception as e:
        print(f"Database record_competition_lesson_answer failed: {e}")
        session.rollback()
        return None, "Could not record answer"
    finally:
        SessionLocal.remove()

def get_competition_scores(session_id):
    if not session_id:
        return []
    session = SessionLocal()
    try:
        sc = CompetitionScore
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
            for row in session.execute(
                select(
                    sc.user_id, User.username, sc.listening_points, sc.reading_points,
                    sc.total_points, sc.total_response_time_ms, sc.rank, sc.finished_at,
                )
                .select_from(sc).join(User, User.id == sc.user_id)
                .where(sc.session_id == session_id)
                .order_by(sc.total_points.desc(), sc.total_response_time_ms.asc(), User.username)
            ).all()
        ]
    except Exception as e:
        print(f"Database get_competition_scores failed: {e}")
        return []
    finally:
        SessionLocal.remove()

def mark_competition_participant_finished(session_id, user_id):
    session = SessionLocal()
    try:
        sc = CompetitionScore
        session.execute(
            update(sc)
            .where(sc.session_id == session_id, sc.user_id == user_id, sc.finished_at.is_(None))
            .values(finished_at=func.now(), updated_at=func.now())
        )
        session.commit()
        return True
    except Exception as e:
        print(f"Database mark_competition_participant_finished failed: {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()

def competition_all_participants_finished(session_id):
    """True when every scored participant has reported finishing their run."""
    session = SessionLocal()
    try:
        sc = CompetitionScore
        row = session.execute(
            select(
                func.count().label("total"),
                func.count().filter(sc.finished_at.isnot(None)).label("done"),
            )
            .where(sc.session_id == session_id)
        ).first()
        total, done = row[0], row[1]
        return bool(total) and int(total) == int(done or 0)
    except Exception as e:
        print(f"Database competition_all_participants_finished failed: {e}")
        return False
    finally:
        SessionLocal.remove()

def finalize_competition_session(session_id):
    """Rank participants, mark the session ranked and free the room back to waiting.
    Called when everyone has finished or the room timer expires. Idempotent: a
    session already ranked is returned as-is."""
    state = get_competition_session_state(session_id)
    if not state:
        return None
    if state["status"] == "ranked":
        return state
    session = SessionLocal()
    try:
        sc = CompetitionScore
        session.execute(
            update(CompetitionSession)
            .where(CompetitionSession.id == session_id)
            .values(status="ranked", finished_at=func.now())
        )
        ranked = (
            select(
                sc.id,
                func.row_number().over(
                    order_by=[
                        sc.total_points.desc(),
                        sc.total_response_time_ms.asc(),
                        func.coalesce(sc.finished_at, func.now()).asc(),
                    ]
                ).label("next_rank"),
            )
            .where(sc.session_id == session_id)
            .subquery("ranked")
        )
        session.execute(
            update(sc)
            .where(sc.id == ranked.c.id)
            .values(rank=ranked.c.next_rank, updated_at=func.now())
        )
        session.execute(
            update(CompetitionRoom)
            .where(
                CompetitionSession.id == session_id,
                CompetitionRoom.id == CompetitionSession.room_id,
            )
            .values(status="waiting", updated_at=func.now())
        )
        session.commit()
        return get_competition_session_state(session_id)
    except Exception as e:
        print(f"Database finalize_competition_session failed: {e}")
        session.rollback()
        return None
    finally:
        SessionLocal.remove()
