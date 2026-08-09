"""
db/records.py
--------------
Queries over the learner activity-record tables (vocab_records, lesson_records,
practice_record) — learned-word mastery and the dashboard time/words charts.
Extracted from the former monolithic db.py.
"""

import json

from sqlalchemy import select, func, distinct, case, union_all, cast, insert, BigInteger
from entity.database import SessionLocal
from entity.record.entity import VocabRecord, LessonRecord, PracticeRecord


def _json_value(value):
    """`vocab_records.game_info` is JSONB but callers pass a JSON string; parse it
    so SQLAlchemy stores real JSON (matching the old psycopg2 text->jsonb cast)."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def get_learned_words(user_id):
    """
    Returns a list of words that have been fully learned by the given user
    (3 correct modes in round 1).
    """
    session = SessionLocal()
    try:
        # daily_attempts: per (word, day) how many of the 3 modes were correct in round 1.
        successful_modes = func.count(
            distinct(case((VocabRecord.is_correct.is_(True), VocabRecord.mode)))
        ).label("successful_modes")
        daily_attempts = (
            select(
                VocabRecord.word.label("word"),
                func.date(VocabRecord.updated_at).label("attempt_date"),
                successful_modes,
            )
            .where(
                VocabRecord.mode.in_(["typing", "listen", "meaning"]),
                VocabRecord.round_num == 1,
                VocabRecord.user_id == user_id,
            )
            .group_by(VocabRecord.word, func.date(VocabRecord.updated_at))
            .cte("daily_attempts")
        )

        # latest_status: keep each word's most recent day only.
        rn = func.row_number().over(
            partition_by=daily_attempts.c.word,
            order_by=daily_attempts.c.attempt_date.desc(),
        ).label("rn")
        latest_status = select(
            daily_attempts.c.word,
            daily_attempts.c.successful_modes,
            rn,
        ).subquery("latest_status")

        stmt = select(latest_status.c.word).where(
            latest_status.c.rn == 1, latest_status.c.successful_modes == 3
        )
        return [row[0] for row in session.execute(stmt).all()]
    except Exception as e:
        print(f"⚠️ Database query failed (get_learned_words): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_learned_words_last_3_days(user_id):
    """
    Cumulative running total of fully-learned words as of each of the 3 most
    recent mastery days.

    A word counts as learned if it reached all 3 correct modes (typing/listen/
    meaning) in round 1 on its most recent practice day (matching get_learned_words).
    The running total sums these masteries by their latest mastery date, and the 3
    most recent mastery days are returned oldest -> newest for a Chart.js chart:
        [{"date": "2026-07-24", "count": 120}, {"date": "2026-07-25", "count": 132}, ...]
    """
    session = SessionLocal()
    try:
        # daily_attempts: per (word, day) how many of the 3 modes were correct in round 1.
        successful_modes = func.count(
            distinct(case((VocabRecord.is_correct.is_(True), VocabRecord.mode)))
        ).label("successful_modes")
        daily_attempts = (
            select(
                VocabRecord.word.label("word"),
                func.date(VocabRecord.updated_at).label("attempt_date"),
                successful_modes,
            )
            .where(
                VocabRecord.mode.in_(["typing", "listen", "meaning"]),
                VocabRecord.round_num == 1,
                VocabRecord.user_id == user_id,
            )
            .group_by(VocabRecord.word, func.date(VocabRecord.updated_at))
            .cte("daily_attempts")
        )

        # mastery: each word's most recent day, kept only if it reached all 3 modes.
        rn = func.row_number().over(
            partition_by=daily_attempts.c.word,
            order_by=daily_attempts.c.attempt_date.desc(),
        ).label("rn")
        ranked = select(
            daily_attempts.c.word,
            daily_attempts.c.attempt_date,
            daily_attempts.c.successful_modes,
            rn,
        ).subquery("ranked")
        mastery = (
            select(ranked.c.word, ranked.c.attempt_date.label("mastered_date"))
            .where(ranked.c.rn == 1, ranked.c.successful_modes == 3)
            .cte("mastery")
        )

        # per_day new masteries, then a running cumulative total by date.
        per_day = (
            select(mastery.c.mastered_date, func.count().label("new_count"))
            .group_by(mastery.c.mastered_date)
            .cte("per_day")
        )
        cumulative_count = func.sum(per_day.c.new_count).over(
            order_by=per_day.c.mastered_date
        ).label("cumulative_count")
        cumulative = select(per_day.c.mastered_date, cumulative_count).cte("cumulative")

        # 3 most recent mastery days, returned oldest -> newest.
        top3 = (
            select(cumulative.c.mastered_date, cumulative.c.cumulative_count)
            .order_by(cumulative.c.mastered_date.desc())
            .limit(3)
            .subquery("top3")
        )
        final = select(top3.c.mastered_date, top3.c.cumulative_count).order_by(
            top3.c.mastered_date.asc()
        )
        rows = session.execute(final).all()
        return [{"date": row[0].isoformat(), "count": int(row[1] or 0)} for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_learned_words_last_3_days): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_time_learned_last_3_days(user_id):
    """
    Total learning time per day for the 3 most recent active days.

    Sums response_time_ms across every answered task (vocab trainer, lesson
    trainer, exercise/exam) grouped by day — the same sources global-stats totals.
    "3 most recent active days" = the 3 latest days that actually have activity
    (gaps are skipped, not zero-filled). Returned oldest -> newest with
    milliseconds and minutes, ready for a Chart.js bar chart:
        [{"date": "2026-07-24", "ms": 3900000, "minutes": 65}, ...]
    """
    session = SessionLocal()
    try:
        # Union the per-answer times across the three activity tables.
        def _per_table(model):
            return select(
                func.date(model.updated_at).label("day"),
                model.response_time_ms.label("ms"),
            ).where(model.user_id == user_id)

        all_time = union_all(
            _per_table(VocabRecord),
            _per_table(LessonRecord),
            _per_table(PracticeRecord),
        ).subquery("all_time")

        total_ms = cast(
            func.coalesce(func.sum(all_time.c.ms), 0), BigInteger
        ).label("total_ms")
        # 3 most recent active days (gaps skipped), returned oldest -> newest.
        per_day = (
            select(all_time.c.day, total_ms)
            .where(all_time.c.day.isnot(None))
            .group_by(all_time.c.day)
            .order_by(all_time.c.day.desc())
            .limit(3)
        )
        rows = sorted(session.execute(per_day).all(), key=lambda r: r[0])
        return [
            {"date": row[0].isoformat(), "ms": int(row[1] or 0), "minutes": round((int(row[1] or 0)) / 60_000)}
            for row in rows
        ]
    except Exception as e:
        print(f"⚠️ Database query failed (get_time_learned_last_3_days): {e}")
        return []
    finally:
        SessionLocal.remove()


# ---------------------------------------------------------------------------
# Writes — record a user's answers into the activity tables.
# ---------------------------------------------------------------------------

def insert_learning_progress(user_id, session_id, mode, word, round_num, game_info, user_answer, is_correct, response_time_ms, updated_at):
    session = SessionLocal()
    try:
        session.execute(insert(VocabRecord).values(
            user_id=user_id,
            session_id=str(session_id),
            mode=mode,
            word=word,
            round_num=round_num,
            game_info=_json_value(game_info),
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            updated_at=updated_at,
        ))
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

    rows = [
        {
            "user_id": user_id,
            "session_id": str(session_id),
            "mode": r.get("mode"),
            "word": r.get("word"),
            "round_num": r.get("round_num", 1),
            "game_info": _json_value(r.get("game_info")),
            "user_answer": r.get("user_answer"),
            "is_correct": r.get("is_correct"),
            "response_time_ms": r.get("response_time_ms", 0),
            "updated_at": updated_at,
        }
        for r in records
    ]
    session = SessionLocal()
    try:
        session.execute(insert(VocabRecord), rows)  # multi-row insert
        session.commit()
    except Exception as e:
        print(f"⚠️ Database batch insert failed: {e}")
        session.rollback()
    finally:
        SessionLocal.remove()


def insert_lesson_progress(user_id, session_id, passage_id, line_id, mode, game_info, user_answer, is_correct, response_time_ms, updated_at):
    # lesson_records.game_info is TEXT — the JSON string is stored as-is.
    session = SessionLocal()
    try:
        session.execute(insert(LessonRecord).values(
            user_id=user_id,
            session_id=str(session_id),
            passage_id=passage_id,
            line_id=line_id,
            mode=mode,
            game_info=game_info,
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            updated_at=updated_at,
        ))
        session.commit()
    except Exception as e:
        print(f"⚠️ Database lesson insert failed: {e}")
        session.rollback()
    finally:
        SessionLocal.remove()


def insert_practice_progress(user_id, session_id, hsk_level, lesson, question_no, skill, question_type, user_answer, is_correct, response_time_ms=None, category='practice'):
    session = SessionLocal()
    try:
        session.execute(insert(PracticeRecord).values(
            user_id=user_id,
            session_id=str(session_id),
            hsk_level=hsk_level,
            lesson=str(lesson),
            question_no=question_no,
            skill=skill,
            question_type=question_type,
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            category=category or 'practice',
        ))
        session.commit()
    except Exception as e:
        print(f"⚠️ Database practice insert failed: {e}")
        session.rollback()
    finally:
        SessionLocal.remove()
