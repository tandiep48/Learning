"""
entity/competition/service.py
--------------------------------
Business logic for the multiplayer "Learn Together" (vocab competition)
feature — rooms, membership, chat, sessions, per-mode scoring and ranking.

Manages the SQLAlchemy session lifecycle (commit/rollback) and shapes
repository rows into the plain dicts callers expect.
"""

import json

from entity.database import SessionLocal
from entity.competition.repository import CompetitionRepository


def resolve_room_words(passage_ids):
    """Union the vocabulary of the selected passages into a deduped word list
    (rows as returned by get_passage_vocab, keyed by 'cn'). Shared by room
    creation (word count) and answer validation."""
    from entity.passage_vocabulary.service import get_passage_vocab
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
                             max_users, section_timeout_minutes):
    session = SessionLocal()
    try:
        repo = CompetitionRepository(session)
        room_id = repo.insert_room(
            room_code, host_user_id, level, passage_ids, word_count,
            max_users, section_timeout_minutes,
        )
        repo.upsert_room_member(room_id, host_user_id, role="host", status="online")
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
        row = CompetitionRepository(session).get_room_row(room_code)
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
    finally:
        SessionLocal.remove()


def join_competition_room(room_code, user_id):
    room = get_competition_room_by_code(room_code)
    if not room:
        return None, "Room not found"
    session = SessionLocal()
    try:
        repo = CompetitionRepository(session)
        active_count = repo.get_active_member_count(room["id"])
        already_member = repo.is_room_member(room["id"], user_id)
        if not already_member and active_count >= int(room["max_users"] or 8):
            return None, "Room is full"

        role = 'host' if int(room["host_user_id"]) == int(user_id) else 'participant'
        repo.upsert_join_member(room["id"], user_id, role)
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
        CompetitionRepository(session).mark_member_left(room["id"], user_id)
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
        repo = CompetitionRepository(session)
        members = [
            {
                "user_id": row[0],
                "username": row[1],
                "role": row[2],
                "status": row[3],
                "joined_at": row[4].isoformat() if row[4] else None,
            }
            for row in repo.get_room_members(room["id"])
        ]

        chat = [
            {
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "message": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }
            for row in reversed(repo.get_recent_chat(room["id"], limit=50))
        ]

        session_row = repo.get_latest_session_row(room["id"])
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


def add_competition_chat_message(room_code, user_id, message):
    room = get_competition_room_by_code(room_code)
    text = str(message or "").strip()[:1000]
    if not room or not text:
        return None
    session = SessionLocal()
    try:
        repo = CompetitionRepository(session)
        row = repo.insert_chat_message(room["id"], user_id, text)
        username = repo.get_username(user_id)
        session.commit()
        return {
            "id": row[0],
            "user_id": user_id,
            "username": username or "User",
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
        return None, "No vocabulary selected"

    session = SessionLocal()
    try:
        repo = CompetitionRepository(session)
        repo.update_room_status(room["id"], "running")
        minutes = int(room["section_timeout_minutes"] or 15)
        session_id = repo.insert_session(room["id"], minutes)
        repo.seed_scores_for_session(session_id, room["id"])
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
        row = CompetitionRepository(session).get_latest_session_id(room["id"])
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
        row = CompetitionRepository(session).get_session_row(session_id)
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
}


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


def record_competition_vocab_answer(session_id, user_id, word, activity_type, is_correct,
                                     response_time_ms, wrong_attempts=0):
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
        repo = CompetitionRepository(session)
        # Only accept answers while the session is running and the user is a scored participant.
        if not repo.is_session_active_for_user(session_id, user_id):
            return None, "Session is not active"

        is_correct = bool(is_correct)
        points = calculate_competition_points(activity_type, is_correct, response_time_ms, wrong_attempts)
        inserted = repo.insert_vocab_answer(
            session_id, user_id, word, activity_type, is_correct, response_time_ms, points
        )
        if not inserted:
            return None, "Answer already submitted"
        repo.increment_score(session_id, user_id, points, response_time_ms)
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


def get_competition_scores(session_id):
    if not session_id:
        return []
    session = SessionLocal()
    try:
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
            for row in CompetitionRepository(session).get_scores_rows(session_id)
        ]
    except Exception as e:
        print(f"Database get_competition_scores failed: {e}")
        return []
    finally:
        SessionLocal.remove()


def mark_competition_participant_finished(session_id, user_id):
    session = SessionLocal()
    try:
        CompetitionRepository(session).mark_score_finished(session_id, user_id)
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
        total, done = CompetitionRepository(session).get_finished_counts(session_id)
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
        repo = CompetitionRepository(session)
        repo.update_session_status(session_id, "ranked", finished=True)
        repo.rank_scores(session_id)
        repo.reopen_room_for_session(session_id)
        session.commit()
        return get_competition_session_state(session_id)
    except Exception as e:
        print(f"Database finalize_competition_session failed: {e}")
        session.rollback()
        return None
    finally:
        SessionLocal.remove()
