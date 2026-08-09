"""
db/learning.py
---------------
Read/reporting queries for a user's vocabulary-learning state and practice
history — mastered words, recommendations, practice sessions, and the
unlearned / unsure / review / hard-word selections.
Extracted from the former monolithic db.py.
"""

from sqlalchemy import (
    select, func, distinct, case, cast, and_, or_, any_, bindparam,
    asc, desc, nullslast, Text, Date, Float, Integer, String,
)
from sqlalchemy.dialects.postgresql import ARRAY

from entity.database import SessionLocal
from entity.record.entity import VocabRecord, PracticeRecord
from entity.vocabulary.entity import Vocabulary
from entity.question.entity import Question
from entity.learning_unit.entity import LearningUnit
from entity.chinese_stroke_info.entity import ChineseStrokeInfo
from entity.sematic_difficulty.entity import SemanticDifficulty
from db.records import get_learned_words


# Shared mastery CTE building blocks (3-mode round-1 rule, latest day per word).
_MASTERY_MODES = ["typing", "listen", "meaning"]


def get_mastered_words_with_recency(conn, user_id):
    """
    Returns mastered words with the timestamp of the latest mastered learning day
    (word + learned_at only). Uses the same 3-mode round-1 mastery rule as
    get_learned_words(). Kept lightweight — no vocabulary join — since callers only
    need the word and its recency; per-word details come from get_mastered_words_page().
    """
    if not conn:
        return []

    session = SessionLocal()
    try:
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
        latest = select(
            daily.c.word, daily.c.learned_at, daily.c.successful_modes, rn
        ).subquery("latest_status")
        stmt = select(latest.c.word, latest.c.learned_at).where(
            latest.c.rn == 1, latest.c.successful_modes == 3
        )
        return [{"word": r[0], "learned_at": r[1]} for r in session.execute(stmt).all()]
    except Exception as e:
        print(f"⚠️ Database query failed (get_mastered_words_with_recency): {e}")
        return []
    finally:
        SessionLocal.remove()

def get_mastered_words_page(conn, user_id, page=1, page_size=24):
    """
    Returns one page of mastered words with the timestamp of the latest mastered learning day.
    Uses the same 3-mode round-1 mastery rule as get_learned_words().
    """
    page_size = min(100, max(1, int(page_size or 24)))
    page = max(1, int(page or 1))
    if not conn:
        return {"rows": [], "page": 1, "page_size": page_size, "total": 0, "total_pages": 1}

    session = SessionLocal()
    try:
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
        latest = select(
            daily.c.word, daily.c.learned_at, daily.c.successful_modes, rn
        ).subquery("latest_status")
        mastered = (
            select(latest.c.word, latest.c.learned_at)
            .where(latest.c.rn == 1, latest.c.successful_modes == 3)
            .cte("mastered")
        )

        total = int(session.execute(select(func.count()).select_from(mastered)).scalar() or 0)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size

        rows = session.execute(
            select(
                mastered.c.word, mastered.c.learned_at,
                Vocabulary.pinyin, Vocabulary.meaning_vn, Vocabulary.meaning_en,
                Vocabulary.audio_key, Vocabulary.hsk_level,
            )
            .select_from(mastered)
            .outerjoin(Vocabulary, Vocabulary.cn == mastered.c.word)
            .order_by(nullslast(mastered.c.learned_at.desc()), mastered.c.word)
            .limit(page_size)
            .offset(offset)
        ).all()

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
    finally:
        SessionLocal.remove()


def get_recommended_practices(conn, user_id, threshold=0.80, limit=None, status_filter=None):
    """
    Returns practice progress groups the user is ready for.
    Uses question_bank + learning_units + vocab_records — NO CSV loading.

    A group is recommended when coverage = known_words/total_words >= threshold,
    measured over the user's ENTIRE mastered-word set (no recency or HSK-level bias).
    Groups are ordered by coverage (highest first).

    Returns list of dicts:
      {level, lesson, progress, skill, type, category, status, unit_ids,
       total_words, known_words, coverage, coverage_pct, matched_words, question_count}
    """
    if not conn:
        return []

    session = SessionLocal()
    try:
        # 1. Every mastered word (3-mode round-1 rule). No recency or HSK-level bias —
        #    the whole mastered set drives coverage.
        mastered = get_learned_words(conn, user_id)
        if not mastered:
            return []
        mastered_list = list(mastered)

        # 2. Coverage per (category, level, lesson, progress) across the whole practice/exam
        #    bank. Dedupe to distinct (group, word) pairs first so the aggregate is a plain
        #    COUNT(*) over distinct words (hash-aggregatable) — avoids the disk-spilling sort
        #    that COUNT(DISTINCT)/ARRAY_AGG(DISTINCT) forces. matched_words holds only the
        #    user's mastered words for that group. `= ANY(:array)` keeps the mastered set as a
        #    single bound array param rather than an expanded IN-list.
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
            bindparam("mastered", value=mastered_list, type_=ARRAY(String))
        )
        coverage_stmt = (
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
        group_coverage = {
            (row[0], row[1], row[2], row[3]): {
                'total_words': row[4],
                'known_words': row[5],
                'coverage': row[5] / row[4],
                'matched_words': row[6] or []
            }
            for row in session.execute(coverage_stmt).all()
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

        # Per-session score, categorised the same way the practice screen records it.
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
                    bindparam("levels", value=ready_levels, type_=ARRAY(Integer))
                ),
                PracticeRecord.lesson == any_(
                    bindparam("lessons", value=ready_lessons, type_=ARRAY(String))
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
        status_stmt = select(
            latest.c.category, latest.c.hsk_level, latest.c.lesson,
            latest.c.progress, latest.c.pct,
        ).where(latest.c.rn == 1)

        lesson_status = {}
        for r in session.execute(status_stmt).all():
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
            data = group_coverage[(category, level, lesson, progress)]
            summaries.append({
                'level':        level,
                'lesson':       lesson,
                'progress':     progress,
                'category':     category,
                'status':       status,
                'total_words':  data['total_words'],
                'known_words':  data['known_words'],
                'coverage':     round(data['coverage'], 4),
                'coverage_pct': round(data['coverage'] * 100, 1),
                'matched_words': sorted(data['matched_words']),
            })

        # Order by coverage (highest first); stable tie-break on level/lesson/progress so the
        # list is deterministic between calls.
        summaries.sort(key=lambda s: (s['level'], s['lesson'], str(s['progress'])))
        summaries.sort(key=lambda s: s['coverage'], reverse=True)
        if limit:
            summaries = summaries[:limit]
        if not summaries:
            return []

        # Fetch only lightweight per-group metadata (count + representative skill/type +
        # unit ids). The full question payloads aren't needed here — the practice screen
        # loads them on demand — so we avoid pulling every question's TEXT/JSONB columns.
        group_conds = or_(*[
            and_(
                Question.category == item['category'],
                Question.level == item['level'],
                Question.lesson == item['lesson'],
                Question.progress == item['progress'],
            )
            for item in summaries
        ])
        meta_stmt = (
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
        meta_by_key = {
            (r[0], r[1], r[2], r[3]): {
                'question_count': r[4],
                'skill':          r[5] or 'listening',
                'type':           r[6],
                'unit_ids':       sorted(r[7] or []),
            }
            for r in session.execute(meta_stmt).all()
        }

        results = []
        for item in summaries:
            key = (item['category'], item['level'], item['lesson'], item['progress'])
            meta = meta_by_key.get(key)
            if not meta or not meta['question_count']:
                continue
            item['skill'] = meta['skill']
            item['type'] = meta['type']
            item['unit_ids'] = meta['unit_ids']
            item['question_count'] = meta['question_count']
            results.append(item)

        return results

    except Exception as e:
        print(f"[WARN] get_recommended_practices failed: {e}")
        return []
    finally:
        SessionLocal.remove()


def get_practice_history_sessions(conn, user_id, hsk_level=None, category=None,
                                  date=None, sort='recent', page=1, page_size=20):
    """
    List a user's past practice/exam sessions for the review page, with optional
    backend filters (hsk_level, category, date) and ordering. One row per session_id,
    with score and the level(s)/lesson(s) it covered.

    Returns (sessions, has_more). has_more lets the caller do prev/next paging without a
    separate COUNT query (we fetch one extra row and trim it). Scoped to user_id.
    """
    if not conn:
        return [], False

    page = max(1, int(page or 1))
    page_size = min(50, max(1, int(page_size or 20)))
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
    # fetch one extra row to detect a next page
    stmt = stmt.order_by(direction(ended_at), direction(PracticeRecord.session_id)).limit(page_size + 1).offset((page - 1) * page_size)

    session = SessionLocal()
    try:
        rows = session.execute(stmt).all()
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        sessions = []
        for row in rows:
            session_id, ended, total, correct, levels, lessons, categories = row
            total = total or 0
            correct = correct or 0
            sessions.append({
                'session_id':   session_id,
                'ended_at':     ended.isoformat() if ended else None,
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
    finally:
        SessionLocal.remove()


def get_practice_session_detail(conn, user_id, session_id):
    """
    Full detail for one of the user's sessions: every answered question joined back
    to question_bank so the review page can show the prompt, options, correct answer
    and the user's own answer. Scoped to user_id so users only see their own records.
    """
    if not conn:
        return None

    session = SessionLocal()
    try:
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
        cols = ['level', 'lesson', 'no', 'skill', 'type', 'user_answer',
                'is_correct', 'answered_at', 'category', 'content', 'question',
                'answer', 'audio_key', 'image', 'options', 'progress']
        return [dict(zip(cols, r)) for r in session.execute(stmt).all()]
    except Exception as e:
        print(f"[WARN] get_practice_session_detail failed: {e}")
        return None
    finally:
        SessionLocal.remove()


def get_unlearned_words_from_db(conn, user_id):

    """
    Returns a list of words from the user's history that have NOT been fully learned 
    (less than 3 distinct correct modes in round 1).
    """
    if not conn:
        return []

    session = SessionLocal()
    try:
        successful_modes = func.count(
            distinct(case((VocabRecord.is_correct.is_(True), VocabRecord.mode)))
        ).label("successful_modes")
        daily = (
            select(
                VocabRecord.word.label("word"),
                func.date(VocabRecord.updated_at).label("attempt_date"),
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
        latest = select(
            daily.c.word, daily.c.successful_modes, rn
        ).subquery("latest_status")
        stmt = select(latest.c.word).where(
            latest.c.rn == 1, latest.c.successful_modes < 3
        )
        return [r[0] for r in session.execute(stmt).all()]
    except Exception as e:
        print(f"⚠️ Database query failed (get_unlearned_words_from_db): {e}")
        return []
    finally:
        SessionLocal.remove()

def get_unsure_words_from_db(conn, user_id):
    """
    Returns learned words the user answers slowly. For each mastered word, response times are
    z-scored per mode against the baseline of all the user's mastered words on their latest
    mastery day; words whose average z-score >= 1.0 are "unsure". Only meaningful once the user
    has mastered >= 50 words — returns [] below that, to keep the baseline stable.
    """
    if not conn:
        return []

    session = SessionLocal()
    try:
        # daily_attempts: distinct correct modes per (word, day) in round 1.
        successful_modes = func.count(
            distinct(case((VocabRecord.is_correct.is_(True), VocabRecord.mode)))
        ).label("successful_modes")
        daily = (
            select(
                VocabRecord.word.label("word"),
                func.date(VocabRecord.updated_at).label("attempt_date"),
                successful_modes,
            )
            .where(
                VocabRecord.user_id == user_id,
                VocabRecord.round_num == 1,
                VocabRecord.mode.in_(_MASTERY_MODES),
            )
            .group_by(VocabRecord.word, func.date(VocabRecord.updated_at))
            .cte("daily_attempts")
        )

        # latest_status: most recent attempt day per word.
        rn = func.row_number().over(
            partition_by=daily.c.word, order_by=daily.c.attempt_date.desc()
        ).label("rn")
        latest = select(
            daily.c.word, daily.c.attempt_date, daily.c.successful_modes, rn
        ).cte("latest_status")

        # learned_words: words mastered (all 3 modes) on their latest day.
        learned = (
            select(latest.c.word, latest.c.attempt_date)
            .where(latest.c.rn == 1, latest.c.successful_modes == 3)
            .cte("learned_words")
        )

        # Global gate: only meaningful once >= 50 words are mastered.
        total_mastered = select(func.count()).select_from(learned).scalar_subquery()

        # latest_records: correct answers for those words on their mastery day.
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

        # stats: response-time baseline per mode (sample stddev, NULL if zero).
        stats = (
            select(
                latest_records.c.mode.label("mode"),
                func.avg(latest_records.c.response_time_ms).label("avg_rt"),
                func.nullif(func.stddev(latest_records.c.response_time_ms), 0).label("std_rt"),
            )
            .group_by(latest_records.c.mode)
            .cte("stats")
        )

        # z_scores: per-word/mode z-score against the baseline.
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
        return [r[0] for r in session.execute(stmt).all()]
    except Exception as e:
        print(f"⚠️ Database query failed (get_unsure_words_from_db): {e}")
        return []
    finally:
        SessionLocal.remove()

def get_review_words(conn, user_id):
    """
    Combines unsure + unlearned words into one prioritized review list.

    Tiers:
      - 'critical'   : word is in BOTH lists (slow AND not fully mastered)
      - 'unsure'     : mastered but slow to answer
      - 'incomplete' : not yet mastered across all 3 modes

    Returns a list of {"word": str, "reason": str}, critical first; within each tier the
    original ordering from the source functions is preserved.
    """
    if not conn:
        return []

    unsure_list = get_unsure_words_from_db(conn, user_id)
    unlearned_list = get_unlearned_words_from_db(conn, user_id)

    unsure_set = set(unsure_list)
    unlearned_set = set(unlearned_list)

    seen = set()
    result = []

    # Pass 1: 'critical' — in both lists (unsure order primary, then any unlearned-first ones)
    for word in unsure_list:
        if word in unlearned_set and word not in seen:
            result.append({"word": word, "reason": "critical"})
            seen.add(word)
    for word in unlearned_list:
        if word in unsure_set and word not in seen:
            result.append({"word": word, "reason": "critical"})
            seen.add(word)

    # Pass 2: 'unsure' — slow but fully mastered
    for word in unsure_list:
        if word not in seen:
            result.append({"word": word, "reason": "unsure"})
            seen.add(word)

    # Pass 3: 'incomplete' — not yet mastered all 3 modes
    for word in unlearned_list:
        if word not in seen:
            result.append({"word": word, "reason": "incomplete"})
            seen.add(word)

    return result

def get_review_words_flat(conn, user_id):
    """
    Same as get_review_words() but returns a plain prioritized list of word strings
    (critical > unsure > incomplete).
    """
    return [entry["word"] for entry in get_review_words(conn, user_id)]

def get_hard_semantic_learned_words(conn, user_id):
    """
    Returns a list of learned words (by the given user) but difficult in semantic.
    """
    if not conn:
        return []

    session = SessionLocal()
    try:
        # Words answered correctly at least 3 times (any mode/round).
        learned = (
            select(VocabRecord.word.label("word"))
            .where(VocabRecord.is_correct.is_(True), VocabRecord.user_id == user_id)
            .group_by(VocabRecord.word)
            .having(func.count() >= 3)
            .cte("learned_words")
        )
        # vocabulary bridges word -> id -> sematic_diffculty.word_id
        # (the old query referenced a non-existent `chinese_dict`; vocabulary is the intended table).
        stmt = (
            select(learned.c.word)
            .select_from(learned)
            .outerjoin(Vocabulary, learned.c.word == Vocabulary.cn)
            .outerjoin(SemanticDifficulty, Vocabulary.id == SemanticDifficulty.word_id)
            .order_by(nullslast(SemanticDifficulty.sematic_difficulty.desc()))
        )
        # sematic_diffculty has duplicate word_id rows, so dedup while keeping order.
        seen = set()
        words = []
        for (word,) in session.execute(stmt).all():
            if word not in seen:
                seen.add(word)
                words.append(word)
        return words
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_semantic_learned_words): {e}")
        return []
    finally:
        SessionLocal.remove()

def get_hard_stroke_learned_words(conn, user_id):
    """
    Returns a list of learned words (by the given user) but difficult in strokes.
    """
    if not conn:
        return []

    session = SessionLocal()
    try:
        # Words answered correctly at least 3 times (any mode/round).
        learned = (
            select(VocabRecord.word.label("word"))
            .where(VocabRecord.is_correct.is_(True), VocabRecord.user_id == user_id)
            .group_by(VocabRecord.word)
            .having(func.count() >= 3)
            .cte("learned_words")
        )
        # Ordered by stroke difficulty; only chinese_stroke_info feeds the ordering.
        stmt = (
            select(learned.c.word)
            .select_from(learned)
            .outerjoin(ChineseStrokeInfo, learned.c.word == ChineseStrokeInfo.cn)
            .order_by(nullslast(ChineseStrokeInfo.strokes_difficult_cn.desc()))
        )
        return [r[0] for r in session.execute(stmt).all()]
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_stroke_learned_words): {e}")
        return []
    finally:
        SessionLocal.remove()
