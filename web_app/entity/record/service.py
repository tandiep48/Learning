"""
entity/record/service.py
---------------------------
Business logic for the learner activity-record tables: dashboard stats
(learned words, time/word charts, profile totals) and recording answers
submitted by the vocab/lesson/practice trainers.

Manages the SQLAlchemy session lifecycle (commit/rollback) and shapes
repository rows into the plain dicts/tuples callers expect.
"""

import json

from entity.database import SessionLocal
from entity.record.repository import RecordRepository


def _json_value(value):
    """`vocab_records.game_info` is JSONB but callers pass a JSON string; parse it
    so SQLAlchemy stores real JSON (matching the old psycopg2 text->jsonb cast)."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


# ---------------------------------------------------------------------------
# Reads — dashboard stats
# ---------------------------------------------------------------------------

def get_learned_words(user_id):
    """List of words fully learned by the given user (3 correct modes in round 1)."""
    session = SessionLocal()
    try:
        return RecordRepository(session).get_learned_words(user_id)
    except Exception as e:
        print(f"⚠️ Database query failed (get_learned_words): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_learned_words_last_3_days(user_id):
    """
    Cumulative running total of fully-learned words for the 3 most recent
    mastery days, oldest -> newest, ready for a Chart.js chart:
        [{"date": "2026-07-24", "count": 120}, ...]
    """
    session = SessionLocal()
    try:
        rows = RecordRepository(session).get_learned_words_last_3_days(user_id)
        return [{"date": row[0].isoformat(), "count": int(row[1] or 0)} for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_learned_words_last_3_days): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_time_learned_last_3_days(user_id):
    """
    Total learning time per day for the 3 most recent active days, oldest ->
    newest, ready for a Chart.js bar chart:
        [{"date": "2026-07-24", "ms": 3900000, "minutes": 65}, ...]
    """
    session = SessionLocal()
    try:
        rows = RecordRepository(session).get_time_learned_last_3_days(user_id)
        return [
            {"date": row[0].isoformat(), "ms": int(row[1] or 0), "minutes": round((int(row[1] or 0)) / 60_000)}
            for row in rows
        ]
    except Exception as e:
        print(f"⚠️ Database query failed (get_time_learned_last_3_days): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_vocab_record_totals(user_id):
    session = SessionLocal()
    try:
        return RecordRepository(session).get_vocab_record_totals(user_id)
    except Exception as e:
        print(f"⚠️ Database query failed (get_vocab_record_totals): {e}")
        return (0, 0)
    finally:
        SessionLocal.remove()


def get_lesson_record_totals(user_id):
    session = SessionLocal()
    try:
        return RecordRepository(session).get_lesson_record_totals(user_id)
    except Exception as e:
        print(f"⚠️ Database query failed (get_lesson_record_totals): {e}")
        return (0, 0)
    finally:
        SessionLocal.remove()


def get_practice_record_totals_by_category(user_id):
    session = SessionLocal()
    try:
        return RecordRepository(session).get_practice_record_totals_by_category(user_id)
    except Exception as e:
        print(f"⚠️ Database query failed (get_practice_record_totals_by_category): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_lesson_progress_by_mode(user_id, passage_ids):
    """Per-mode attempt/correct/time totals over lesson_records for the given passages."""
    if not passage_ids:
        return []
    session = SessionLocal()
    try:
        rows = RecordRepository(session).get_lesson_progress_by_mode(user_id, passage_ids)
        return [
            {"mode": r[0], "attempts": int(r[1] or 0), "correct": int(r[2] or 0), "time_ms": int(r[3] or 0)}
            for r in rows
        ]
    except Exception as e:
        print(f"⚠️ Database query failed (get_lesson_progress_by_mode): {e}")
        return []
    finally:
        SessionLocal.remove()


# ---------------------------------------------------------------------------
# Writes — record a user's answers into the activity tables.
# ---------------------------------------------------------------------------

def insert_learning_progress(user_id, session_id, mode, word, round_num, game_info, user_answer,
                              is_correct, response_time_ms, updated_at):
    session = SessionLocal()
    try:
        RecordRepository(session).insert_vocab_record(
            user_id=user_id,
            session_id=session_id,
            mode=mode,
            word=word,
            round_num=round_num,
            game_info=_json_value(game_info),
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            updated_at=updated_at,
        )
        session.commit()
    except Exception as e:
        print(f"⚠️ Database insert failed: {e}")
        session.rollback()
    finally:
        SessionLocal.remove()


def insert_learning_progress_batch(user_id, session_id, records, updated_at):
    """
    Bulk-insert several vocab_records rows in one round-trip. Each record is a dict with keys:
    mode, word, round_num, game_info (JSON string), user_answer, is_correct, response_time_ms.
    Used by the batch vocab trainer, which submits a whole group's answers at once.
    """
    if not records:
        return

    normalized = [
        {**r, "game_info": _json_value(r.get("game_info"))}
        for r in records
    ]
    session = SessionLocal()
    try:
        RecordRepository(session).insert_vocab_records_batch(
            user_id=user_id,
            session_id=session_id,
            records=normalized,
            updated_at=updated_at,
        )
        session.commit()
    except Exception as e:
        print(f"⚠️ Database batch insert failed: {e}")
        session.rollback()
    finally:
        SessionLocal.remove()


def insert_lesson_progress(user_id, session_id, passage_id, line_id, mode, game_info, user_answer,
                            is_correct, response_time_ms, updated_at):
    session = SessionLocal()
    try:
        RecordRepository(session).insert_lesson_record(
            user_id=user_id,
            session_id=session_id,
            passage_id=passage_id,
            line_id=line_id,
            mode=mode,
            game_info=game_info,
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            updated_at=updated_at,
        )
        session.commit()
    except Exception as e:
        print(f"⚠️ Database lesson insert failed: {e}")
        session.rollback()
    finally:
        SessionLocal.remove()


def insert_practice_progress(user_id, session_id, hsk_level, lesson, question_no, skill, question_type,
                              user_answer, is_correct, response_time_ms=None, category='practice'):
    session = SessionLocal()
    try:
        RecordRepository(session).insert_practice_record(
            user_id=user_id,
            session_id=session_id,
            hsk_level=hsk_level,
            lesson=lesson,
            question_no=question_no,
            skill=skill,
            question_type=question_type,
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            category=category,
        )
        session.commit()
    except Exception as e:
        print(f"⚠️ Database practice insert failed: {e}")
        session.rollback()
    finally:
        SessionLocal.remove()
