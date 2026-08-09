"""
db/learning.py
---------------
Read/reporting queries for a user's vocabulary-learning state and practice
history — mastered words, recommendations, practice sessions, and the
unlearned / unsure / review / hard-word selections.
Extracted from the former monolithic db.py.
"""

from sqlalchemy import select, func, distinct, case, cast, and_, asc, desc, nullslast, Text, Date

from entity.database import SessionLocal
from entity.record.entity import VocabRecord, PracticeRecord
from entity.vocabulary.entity import Vocabulary
from entity.question.entity import Question
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

    try:
        # 1. Every mastered word (3-mode round-1 rule). No recency or HSK-level bias —
        #    the whole mastered set drives coverage.
        mastered = get_learned_words(conn, user_id)
        if not mastered:
            return []

        # 2. Coverage per (category, level, lesson, progress) across the whole practice/exam
        #    bank. Dedupe to distinct (group, word) pairs first so the aggregate is a plain
        #    COUNT(*) over distinct words (hash-aggregatable) — avoids the disk-spilling sort
        #    that COUNT(DISTINCT)/ARRAY_AGG(DISTINCT) forces. matched_words holds only the
        #    user's mastered words for that group.
        coverage_sql = """
            WITH group_words AS (
                SELECT DISTINCT qb.category, qb.level, qb.lesson, qb.progress, lu.unique_word
                FROM question_bank qb
                JOIN learning_units lu ON lu.unit_id = qb.unit_id
                WHERE qb.category IN ('practice', 'exam')
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
            cur.execute(coverage_sql, (list(mastered), list(mastered)))
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
        where_clauses = []
        params = []
        for item in summaries:
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

    query = """
WITH daily_attempts AS (
    SELECT
        word,
        DATE(updated_at) AS attempt_date,
        COUNT(DISTINCT CASE WHEN is_correct THEN mode END) AS successful_modes
    FROM vocab_records
    WHERE user_id = %s
      AND round_num = 1
      AND mode IN ('typing', 'listen', 'meaning')
    GROUP BY word, DATE(updated_at)
),
latest_status AS (
    SELECT
        word,
        attempt_date,
        successful_modes,
        ROW_NUMBER() OVER (PARTITION BY word ORDER BY attempt_date DESC) AS rn
    FROM daily_attempts
),
learned_words AS (
    SELECT word, attempt_date
    FROM latest_status
    WHERE rn = 1 AND successful_modes = 3
),
mastered_count AS (
    SELECT COUNT(*) AS total_mastered FROM learned_words
),
latest_records AS (
    SELECT v.word, v.mode, v.response_time_ms
    FROM vocab_records v
    JOIN learned_words l
      ON v.word = l.word
     AND DATE(v.updated_at) = l.attempt_date
    WHERE v.user_id = %s
      AND v.round_num = 1
      AND v.is_correct = true
      AND v.mode IN ('typing', 'listen', 'meaning')
),
stats AS (
    SELECT
        mode,
        AVG(response_time_ms) AS avg_rt,
        NULLIF(STDDEV(response_time_ms), 0) AS std_rt
    FROM latest_records
    GROUP BY mode
),
z_scores AS (
    SELECT
        lr.word,
        lr.mode,
        (lr.response_time_ms - s.avg_rt) / s.std_rt AS z_score
    FROM latest_records lr
    JOIN stats s ON lr.mode = s.mode
    WHERE s.std_rt IS NOT NULL
)
SELECT
    z.word,
    AVG(z.z_score) AS avg_z_score
FROM z_scores z
CROSS JOIN mastered_count mc
WHERE mc.total_mastered >= 50
GROUP BY z.word
HAVING AVG(z.z_score) >= 1.0
ORDER BY avg_z_score DESC;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, user_id))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_unsure_words_from_db): {e}")
        return []

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
