"""
entity/record/repository.py
-----------------------------
All database queries and mutations for the learner activity-record tables
(vocab_records, lesson_records, practice_record) using SQLAlchemy ORM.

No raw SQL strings — all queries go through the ORM session. Session
lifecycle (commit/rollback/remove) is owned by the service layer.
"""

from sqlalchemy import select, func, distinct, case, union_all, cast, insert, BigInteger
from sqlalchemy.orm import Session

from entity.record.entity import VocabRecord, LessonRecord, PracticeRecord


class RecordRepository:
    """Encapsulates all queries/mutations for the activity-record tables."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_learned_words(self, user_id):
        """
        Words fully learned by the user (3 correct modes in round 1), latest
        mastery day per word only.
        """
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
        return [row[0] for row in self.session.execute(stmt).all()]

    def get_learned_words_last_3_days(self, user_id):
        """
        Cumulative running total of fully-learned words as of each of the 3
        most recent mastery days, oldest -> newest.
        """
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

        per_day = (
            select(mastery.c.mastered_date, func.count().label("new_count"))
            .group_by(mastery.c.mastered_date)
            .cte("per_day")
        )
        cumulative_count = func.sum(per_day.c.new_count).over(
            order_by=per_day.c.mastered_date
        ).label("cumulative_count")
        cumulative = select(per_day.c.mastered_date, cumulative_count).cte("cumulative")

        top3 = (
            select(cumulative.c.mastered_date, cumulative.c.cumulative_count)
            .order_by(cumulative.c.mastered_date.desc())
            .limit(3)
            .subquery("top3")
        )
        final = select(top3.c.mastered_date, top3.c.cumulative_count).order_by(
            top3.c.mastered_date.asc()
        )
        return self.session.execute(final).all()

    def get_time_learned_last_3_days(self, user_id):
        """
        (day, total_ms) for the 3 most recent active days (gaps skipped),
        summed across all three activity tables, oldest -> newest.
        """
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
        per_day = (
            select(all_time.c.day, total_ms)
            .where(all_time.c.day.isnot(None))
            .group_by(all_time.c.day)
            .order_by(all_time.c.day.desc())
            .limit(3)
        )
        return sorted(self.session.execute(per_day).all(), key=lambda r: r[0])

    def _record_totals(self, model, user_id):
        """(count, total_response_time_ms) across one activity table for a user."""
        row = self.session.execute(
            select(
                func.count(),
                cast(func.coalesce(func.sum(model.response_time_ms), 0), BigInteger),
            ).where(model.user_id == user_id)
        ).first()
        return (int(row[0] or 0), int(row[1] or 0))

    def get_vocab_record_totals(self, user_id):
        return self._record_totals(VocabRecord, user_id)

    def get_lesson_record_totals(self, user_id):
        return self._record_totals(LessonRecord, user_id)

    def get_practice_record_totals_by_category(self, user_id):
        """[(category, count, time_ms), ...] over practice_record for a user."""
        cat = func.coalesce(PracticeRecord.category, "practice")
        rows = self.session.execute(
            select(
                cat,
                func.count(),
                cast(func.coalesce(func.sum(PracticeRecord.response_time_ms), 0), BigInteger),
            )
            .where(PracticeRecord.user_id == user_id)
            .group_by(cat)
        ).all()
        return [(str(r[0]), int(r[1] or 0), int(r[2] or 0)) for r in rows]

    def get_lesson_progress_by_mode(self, user_id, passage_ids):
        """Per-mode attempt/correct/time totals over lesson_records for the given passages."""
        if not passage_ids:
            return []
        rows = self.session.execute(
            select(
                LessonRecord.mode,
                func.count().label("attempts"),
                func.coalesce(func.sum(case((LessonRecord.is_correct, 1), else_=0)), 0).label("correct"),
                cast(func.coalesce(func.sum(LessonRecord.response_time_ms), 0), BigInteger).label("time_ms"),
            )
            .where(LessonRecord.user_id == user_id, LessonRecord.passage_id.in_(passage_ids))
            .group_by(LessonRecord.mode)
            .order_by(LessonRecord.mode)
        ).all()
        return rows

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def insert_vocab_record(self, user_id, session_id, mode, word, round_num, game_info,
                             user_answer, is_correct, response_time_ms, updated_at):
        self.session.execute(insert(VocabRecord).values(
            user_id=user_id,
            session_id=str(session_id),
            mode=mode,
            word=word,
            round_num=round_num,
            game_info=game_info,
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            updated_at=updated_at,
        ))

    def insert_vocab_records_batch(self, user_id, session_id, records, updated_at):
        """Bulk-insert several vocab_records rows in one round-trip.

        `records` items are already-normalized dicts with keys: mode, word,
        round_num, game_info, user_answer, is_correct, response_time_ms.
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
                "game_info": r.get("game_info"),
                "user_answer": r.get("user_answer"),
                "is_correct": r.get("is_correct"),
                "response_time_ms": r.get("response_time_ms", 0),
                "updated_at": updated_at,
            }
            for r in records
        ]
        self.session.execute(insert(VocabRecord), rows)  # multi-row insert

    def insert_lesson_record(self, user_id, session_id, passage_id, line_id, mode, game_info,
                              user_answer, is_correct, response_time_ms, updated_at):
        # lesson_records.game_info is TEXT — the JSON string is stored as-is.
        self.session.execute(insert(LessonRecord).values(
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

    def insert_practice_record(self, user_id, session_id, hsk_level, lesson, question_no, skill,
                                question_type, user_answer, is_correct, response_time_ms=None,
                                category='practice'):
        self.session.execute(insert(PracticeRecord).values(
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
