"""
entity/learning/repository.py
------------------------------
All database queries for a user's vocabulary-learning state and practice
history using SQLAlchemy ORM — mastered words, practice recommendations,
practice sessions, and the unlearned / unsure / hard-word selections.

No raw SQL strings — all queries go through the ORM session. Session
lifecycle (commit/rollback/remove) is owned by the service layer.
"""

from sqlalchemy import (
    select, func, distinct, case, cast, and_, or_, any_, bindparam,
    asc, desc, nullslast, Text, Date, Float, Integer, String,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from entity.record.entity import VocabRecord, PracticeRecord
from entity.vocabulary.entity import Vocabulary
from entity.question.entity import Question
from entity.learning_unit.entity import LearningUnit
from entity.chinese_stroke_info.entity import ChineseStrokeInfo
from entity.sematic_difficulty.entity import SemanticDifficulty

# Shared mastery rule (3-mode round-1, latest attempt day per word).
_MASTERY_MODES = ["typing", "listen", "meaning"]


class LearningRepository:
    """Encapsulates all queries for the vocab-learning/practice-stats tables."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Shared building blocks
    # ------------------------------------------------------------------

    def _latest_attempt_status(self, user_id):
        """Subquery: one row per word's most recent attempt day (mode/round-1), with
        successful_modes = distinct correct modes attempted that day, and a row_number
        `rn` (1 = latest day) so callers can filter to just that day per word."""
        successful_modes = func.count(
            distinct(case((VocabRecord.is_correct.is_(True), VocabRecord.mode)))
        ).label("successful_modes")
        daily = (
            select(
                VocabRecord.word.label("word"),
                func.date(VocabRecord.updated_at).label("attempt_date"),
                func.max(VocabRecord.updated_at).label("learned_at"),
                successful_modes,
            )
            .where(
                VocabRecord.mode.in_(_MASTERY_MODES),
                VocabRecord.round_num == 1,
                VocabRecord.user_id == user_id,
            )
            .group_by(VocabRecord.word, func.date(VocabRecord.updated_at))
            .cte("daily_attempts")
        )
        rn = func.row_number().over(
            partition_by=daily.c.word, order_by=daily.c.attempt_date.desc()
        ).label("rn")
        return select(
            daily.c.word, daily.c.attempt_date, daily.c.learned_at,
            daily.c.successful_modes, rn,
        ).subquery("latest_status")

    def _mastered_words_cte(self, user_id):
        """CTE: (word, learned_at) for words mastered (3/3 modes) on their latest day."""
        latest = self._latest_attempt_status(user_id)
        return (
            select(latest.c.word, latest.c.learned_at)
            .where(latest.c.rn == 1, latest.c.successful_modes == 3)
            .cte("mastered")
        )

    # ------------------------------------------------------------------
    # Mastered words
    # ------------------------------------------------------------------

    def get_mastered_words_with_recency(self, user_id):
        """(word, learned_at) rows for every mastered word — no vocabulary join."""
        latest = self._latest_attempt_status(user_id)
        stmt = select(latest.c.word, latest.c.learned_at).where(
            latest.c.rn == 1, latest.c.successful_modes == 3
        )
        return self.session.execute(stmt).all()

    def get_mastered_words_total(self, user_id):
        mastered = self._mastered_words_cte(user_id)
        return int(self.session.execute(select(func.count()).select_from(mastered)).scalar() or 0)

    def get_mastered_words_rows(self, user_id, limit, offset):
        """One page of mastered words joined to vocabulary for per-word details."""
        mastered = self._mastered_words_cte(user_id)
        stmt = (
            select(
                mastered.c.word, mastered.c.learned_at,
                Vocabulary.pinyin, Vocabulary.meaning_vn, Vocabulary.meaning_en,
                Vocabulary.audio_key, Vocabulary.hsk_level,
            )
            .select_from(mastered)
            .outerjoin(Vocabulary, Vocabulary.cn == mastered.c.word)
            .order_by(nullslast(mastered.c.learned_at.desc()), mastered.c.word)
            .limit(limit)
            .offset(offset)
        )
        return self.session.execute(stmt).all()

    # ------------------------------------------------------------------
    # Unlearned / unsure words
    # ------------------------------------------------------------------

    def get_unlearned_words(self, user_id):
        """Words whose latest attempt day has fewer than 3 distinct correct modes."""
        latest = self._latest_attempt_status(user_id)
        stmt = select(latest.c.word).where(latest.c.rn == 1, latest.c.successful_modes < 3)
        return [r[0] for r in self.session.execute(stmt).all()]

    def get_unsure_words(self, user_id):
        """Mastered words whose response times z-score >= 1.0 against the baseline of all
        the user's mastered words on their latest mastery day. [] below 50 mastered words."""
        latest = self._latest_attempt_status(user_id)
        learned = (
            select(latest.c.word, latest.c.attempt_date)
            .where(latest.c.rn == 1, latest.c.successful_modes == 3)
            .cte("learned_words")
        )
        total_mastered = select(func.count()).select_from(learned).scalar_subquery()

        latest_records = (
            select(
                VocabRecord.word.label("word"),
                VocabRecord.mode.label("mode"),
                VocabRecord.response_time_ms.label("response_time_ms"),
            )
            .select_from(VocabRecord)
            .join(
                learned,
                and_(
                    VocabRecord.word == learned.c.word,
                    func.date(VocabRecord.updated_at) == learned.c.attempt_date,
                ),
            )
            .where(
                VocabRecord.user_id == user_id,
                VocabRecord.round_num == 1,
                VocabRecord.is_correct.is_(True),
                VocabRecord.mode.in_(_MASTERY_MODES),
            )
            .cte("latest_records")
        )

        stats = (
            select(
                latest_records.c.mode.label("mode"),
                func.avg(latest_records.c.response_time_ms).label("avg_rt"),
                func.nullif(func.stddev(latest_records.c.response_time_ms), 0).label("std_rt"),
            )
            .group_by(latest_records.c.mode)
            .cte("stats")
        )

        z_scores = (
            select(
                latest_records.c.word.label("word"),
                latest_records.c.mode.label("mode"),
                ((latest_records.c.response_time_ms - stats.c.avg_rt) / stats.c.std_rt).label("z_score"),
            )
            .select_from(latest_records)
            .join(stats, latest_records.c.mode == stats.c.mode)
            .where(stats.c.std_rt.isnot(None))
            .cte("z_scores")
        )

        avg_z = func.avg(z_scores.c.z_score).label("avg_z_score")
        stmt = (
            select(z_scores.c.word, avg_z)
            .where(total_mastered >= 50)
            .group_by(z_scores.c.word)
            .having(func.avg(z_scores.c.z_score) >= 1.0)
            .order_by(avg_z.desc())
        )
        return [r[0] for r in self.session.execute(stmt).all()]

    # ------------------------------------------------------------------
    # Practice recommendations
    # ------------------------------------------------------------------

    def get_group_words_coverage(self, mastered_words):
        """Coverage (total/known/matched words) per (category, level, lesson, progress)
        group across the whole practice/exam question bank, given the user's full
        mastered-word set."""
        group_words = (
            select(
                Question.category, Question.level, Question.lesson,
                Question.progress, LearningUnit.unique_word,
            )
            .select_from(Question)
            .join(LearningUnit, LearningUnit.unit_id == Question.unit_id)
            .where(Question.category.in_(["practice", "exam"]))
            .distinct()
            .cte("group_words")
        )
        known = group_words.c.unique_word == any_(
            bindparam("mastered", value=mastered_words, type_=ARRAY(String))
        )
        stmt = (
            select(
                group_words.c.category, group_words.c.level, group_words.c.lesson,
                group_words.c.progress,
                func.count().label("total_words"),
                func.count().filter(known).label("known_words"),
                func.array_agg(group_words.c.unique_word).filter(known).label("matched_words"),
            )
            .group_by(
                group_words.c.category, group_words.c.level,
                group_words.c.lesson, group_words.c.progress,
            )
        )
        return self.session.execute(stmt).all()

    def get_group_latest_status(self, user_id, levels, lessons):
        """Latest session score per (category, hsk_level, lesson, progress) group,
        restricted to the given levels/lessons so the scan doesn't cover the user's
        entire practice history."""
        cat_expr = func.coalesce(
            PracticeRecord.category, cast(Question.category, Text), "practice"
        )
        pct_expr = (
            cast(func.sum(case((PracticeRecord.is_correct, 1), else_=0)), Float)
            / func.count()
        )
        session_results = (
            select(
                cat_expr.label("category"),
                PracticeRecord.hsk_level.label("hsk_level"),
                PracticeRecord.lesson.label("lesson"),
                Question.progress.label("progress"),
                PracticeRecord.session_id.label("session_id"),
                pct_expr.label("pct"),
                func.max(PracticeRecord.created_at).label("session_end"),
            )
            .select_from(PracticeRecord)
            .outerjoin(
                Question,
                and_(
                    Question.level == PracticeRecord.hsk_level,
                    cast(Question.lesson, Text) == cast(PracticeRecord.lesson, Text),
                    Question.no == PracticeRecord.question_no,
                    cast(Question.category, Text) == func.coalesce(PracticeRecord.category, "practice"),
                ),
            )
            .where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.hsk_level == any_(
                    bindparam("levels", value=levels, type_=ARRAY(Integer))
                ),
                PracticeRecord.lesson == any_(
                    bindparam("lessons", value=lessons, type_=ARRAY(String))
                ),
            )
            .group_by(
                cat_expr, PracticeRecord.hsk_level, PracticeRecord.lesson,
                Question.progress, PracticeRecord.session_id,
            )
            .cte("session_results")
        )
        rn = func.row_number().over(
            partition_by=[
                session_results.c.category, session_results.c.hsk_level,
                session_results.c.lesson, session_results.c.progress,
            ],
            order_by=session_results.c.session_end.desc(),
        ).label("rn")
        latest = select(
            session_results.c.category, session_results.c.hsk_level,
            session_results.c.lesson, session_results.c.progress,
            session_results.c.pct, rn,
        ).cte("latest")
        stmt = select(
            latest.c.category, latest.c.hsk_level, latest.c.lesson,
            latest.c.progress, latest.c.pct,
        ).where(latest.c.rn == 1)
        return self.session.execute(stmt).all()

    def get_group_metadata(self, groups):
        """Lightweight per-group metadata (question count, representative skill/type,
        unit ids) for the given (category, level, lesson, progress) group keys."""
        if not groups:
            return []
        group_conds = or_(*[
            and_(
                Question.category == category,
                Question.level == level,
                Question.lesson == lesson,
                Question.progress == progress,
            )
            for category, level, lesson, progress in groups
        ])
        stmt = (
            select(
                Question.category, Question.level, Question.lesson, Question.progress,
                func.count().label("question_count"),
                func.mode().within_group(Question.skill).label("skill"),
                func.min(Question.type).label("type"),
                func.array_agg(distinct(Question.unit_id)).label("unit_ids"),
            )
            .where(group_conds)
            .group_by(Question.category, Question.level, Question.lesson, Question.progress)
        )
        return self.session.execute(stmt).all()

    # ------------------------------------------------------------------
    # Practice history
    # ------------------------------------------------------------------

    def list_practice_sessions(self, user_id, hsk_level, category, date, sort, page, page_size):
        """One row per session_id for the user's practice/exam history, newest/oldest
        first per `sort`. Fetches one extra row past page_size so the caller can detect
        a next page without a separate COUNT query."""
        direction = asc if sort == 'oldest' else desc
        ended_at = func.max(PracticeRecord.created_at)

        where = [PracticeRecord.user_id == user_id]
        if category in ('practice', 'exam'):
            where.append(func.coalesce(PracticeRecord.category, 'practice') == category)

        # Level can vary within a multi-lesson session, so keep the whole session (with its
        # full score) as long as it touched the requested level. Date matches the session's
        # end day. Both are HAVING conditions so session stats stay complete.
        having = []
        if hsk_level is not None:
            having.append(func.bool_or(PracticeRecord.hsk_level == hsk_level))
        if date:
            having.append(cast(ended_at, Date) == date)

        stmt = (
            select(
                PracticeRecord.session_id,
                ended_at.label("ended_at"),
                func.count().label("total"),
                func.sum(case((PracticeRecord.is_correct, 1), else_=0)).label("correct"),
                func.array_agg(distinct(PracticeRecord.hsk_level)).label("levels"),
                func.array_agg(distinct(PracticeRecord.lesson)).label("lessons"),
                func.array_agg(distinct(func.coalesce(PracticeRecord.category, 'practice'))).label("categories"),
            )
            .where(and_(*where))
            .group_by(PracticeRecord.session_id)
        )
        if having:
            stmt = stmt.having(and_(*having))
        stmt = (
            stmt.order_by(direction(ended_at), direction(PracticeRecord.session_id))
            .limit(page_size + 1)
            .offset((page - 1) * page_size)
        )
        return self.session.execute(stmt).all()

    def get_practice_session_rows(self, user_id, session_id):
        """Every answered question in one of the user's sessions, joined to
        question_bank for the prompt, options, correct answer and the user's answer."""
        stmt = (
            select(
                PracticeRecord.hsk_level, PracticeRecord.lesson, PracticeRecord.question_no,
                PracticeRecord.skill, PracticeRecord.question_type, PracticeRecord.user_answer,
                PracticeRecord.is_correct, PracticeRecord.created_at,
                func.coalesce(PracticeRecord.category, 'practice').label("category"),
                Question.content, Question.question, Question.answer, Question.audio_key,
                Question.image, Question.options, Question.progress,
            )
            .select_from(PracticeRecord)
            .outerjoin(
                Question,
                and_(
                    Question.level == PracticeRecord.hsk_level,
                    cast(Question.lesson, Text) == cast(PracticeRecord.lesson, Text),
                    Question.no == PracticeRecord.question_no,
                    cast(Question.category, Text) == func.coalesce(PracticeRecord.category, 'practice'),
                ),
            )
            .where(PracticeRecord.user_id == user_id, PracticeRecord.session_id == session_id)
            .order_by(
                PracticeRecord.hsk_level, PracticeRecord.lesson, Question.progress,
                PracticeRecord.question_no, PracticeRecord.created_at,
            )
        )
        return self.session.execute(stmt).all()

    # ------------------------------------------------------------------
    # Hard words (semantic / stroke difficulty)
    # ------------------------------------------------------------------

    def get_hard_semantic_words_ordered(self, user_id, min_correct=3):
        """Learned words (>= min_correct correct answers, any mode/round) ordered by
        semantic difficulty (hardest first). May contain duplicate words — the
        `sematic_diffculty` table has duplicate word_id rows."""
        learned = (
            select(VocabRecord.word.label("word"))
            .where(VocabRecord.is_correct.is_(True), VocabRecord.user_id == user_id)
            .group_by(VocabRecord.word)
            .having(func.count() >= min_correct)
            .cte("learned_words")
        )
        stmt = (
            select(learned.c.word)
            .select_from(learned)
            .outerjoin(Vocabulary, learned.c.word == Vocabulary.cn)
            .outerjoin(SemanticDifficulty, Vocabulary.id == SemanticDifficulty.word_id)
            .order_by(nullslast(SemanticDifficulty.sematic_difficulty.desc()))
        )
        return [r[0] for r in self.session.execute(stmt).all()]

    def get_hard_stroke_words_ordered(self, user_id, min_correct=3):
        """Learned words (>= min_correct correct answers, any mode/round) ordered by
        stroke difficulty (hardest first)."""
        learned = (
            select(VocabRecord.word.label("word"))
            .where(VocabRecord.is_correct.is_(True), VocabRecord.user_id == user_id)
            .group_by(VocabRecord.word)
            .having(func.count() >= min_correct)
            .cte("learned_words")
        )
        stmt = (
            select(learned.c.word)
            .select_from(learned)
            .outerjoin(ChineseStrokeInfo, learned.c.word == ChineseStrokeInfo.cn)
            .order_by(nullslast(ChineseStrokeInfo.strokes_difficult_cn.desc()))
        )
        return [r[0] for r in self.session.execute(stmt).all()]
