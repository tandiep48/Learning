import os
import psycopg2
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
    Returns mastered words with the timestamp of the latest mastered learning day.
    Uses the same 3-mode round-1 mastery rule as get_learned_words().
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
    SELECT ls.word, ls.learned_at, v.pinyin, v.meaning_vn, v.meaning_en, v.hsk_level
    FROM latest_status ls
    LEFT JOIN vocabulary v ON ls.word = v.cn
    WHERE ls.rn = 1 AND ls.successful_modes = 3;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
            return [
                {
                    "word": row[0],
                    "learned_at": row[1],
                    "pinyin": row[2] or "",
                    "meaning_vn": row[3] or "",
                    "meaning_en": row[4] or "",
                    "hsk_level": row[5] or ""
                }
                for row in rows
            ]
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
    SELECT word, learned_at, COUNT(*) OVER() AS total
    FROM mastered
    ORDER BY learned_at DESC NULLS LAST, word
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
                    "learned_at": row[1].isoformat() if hasattr(row[1], "isoformat") else row[1]
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

def get_recommended_practices(conn, user_id, threshold=0.75):
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
        # 1. Get mastered words (3-mode logic) — from vocab_records only
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

        # 2. Compute coverage per progress group — includes both practice and exam
        coverage_sql = """
            SELECT
                qb.category, qb.level, qb.lesson, qb.progress,
                COUNT(DISTINCT lu.unique_word)                                              AS total_words,
                COUNT(DISTINCT CASE WHEN lu.unique_word = ANY(%s) THEN lu.unique_word END)  AS known_words,
                ARRAY_AGG(DISTINCT lu.unique_word)                                          AS group_words
            FROM learning_units lu
            JOIN question_bank qb ON lu.unit_id = qb.unit_id
            WHERE qb.category IN ('practice', 'exam')
            GROUP BY qb.category, qb.level, qb.lesson, qb.progress
            HAVING COUNT(DISTINCT lu.unique_word) > 0
        """
        with conn.cursor() as cur:
            cur.execute(coverage_sql, (list(mastered),))
            group_coverage = {
                (row[0], row[1], row[2], row[3]): {
                    'total_words': row[4],
                    'known_words': row[5],
                    'coverage': row[5] / row[4],
                    'group_words': row[6] or []
                }
                for row in cur.fetchall()
                if row[4] > 0
            }

        # 3. Filter groups meeting threshold
        ready_keys = {k for k, d in group_coverage.items() if d['coverage'] >= threshold}
        if not ready_keys:
            return []

        # 4. Fetch all questions for ready groups
        where_clauses = []
        params = []
        for cat, lvl, les, prog in ready_keys:
            where_clauses.append("(category = %s AND level = %s AND lesson = %s AND progress = %s)")
            params.extend([cat, lvl, les, prog])
        
        questions_sql = f"""
            SELECT level, lesson, progress, skill, type, unit_id,
                   no, content, question, answer, audio_key, image, options, category
            FROM question_bank
            WHERE {' OR '.join(where_clauses)}
            ORDER BY level, lesson, no
        """
        with conn.cursor() as cur:
            cur.execute(questions_sql, params)
            cols = ['level', 'lesson', 'progress', 'skill', 'type', 'unit_id',
                    'no', 'content', 'question', 'answer', 'audio_key', 'image', 'options', 'category']
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        # 5. Group by (category, level, lesson, progress)
        from collections import defaultdict
        groups = defaultdict(lambda: {'questions': [], 'unit_ids': set()})
        for r in rows:
            key = (r['category'], r['level'], r['lesson'], r['progress'])
            groups[key]['questions'].append(r)
            groups[key]['unit_ids'].add(r['unit_id'])

        # 6. Find latest sessions to determine status
        with conn.cursor() as cur:
            cur.execute("""
                WITH session_results AS (
                    SELECT hsk_level, lesson, session_id,
                           SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::float / COUNT(*) AS pct,
                           MAX(created_at) AS session_end
                    FROM practice_record WHERE user_id = %s
                    GROUP BY hsk_level, lesson, session_id
                ),
                latest AS (
                    SELECT hsk_level, lesson, pct,
                           ROW_NUMBER() OVER (PARTITION BY hsk_level, lesson ORDER BY session_end DESC) AS rn
                    FROM session_results
                )
                SELECT hsk_level::int, lesson::int, pct FROM latest WHERE rn = 1
            """, (user_id,))
            lesson_status = {}
            for r in cur.fetchall():
                lvl, les, pct = int(r[0]), int(r[1]), r[2]
                if pct == 1.0:
                    lesson_status[(lvl, les)] = "Finish and success"
                else:
                    lesson_status[(lvl, les)] = "Finish and fail"

        # 7. Build results — one per progress group
        results = []
        for (category, level, lesson, progress), gdata in groups.items():
            status = lesson_status.get((level, lesson), "Not start")
            qs = gdata['questions']
            total = group_coverage[(category, level, lesson, progress)]['total_words']
            known = group_coverage[(category, level, lesson, progress)]['known_words']
            coverage = group_coverage[(category, level, lesson, progress)]['coverage']
            group_words = group_coverage[(category, level, lesson, progress)]['group_words']
            matched_words = sorted({word for word in group_words if word in mastered_recency})
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
            
            first = qs[0]
            # Derive skill via majority vote — avoids NULL first-row mislabelling
            skills = [q.get('skill') for q in qs if q.get('skill')]
            skill = max(set(skills), key=skills.count) if skills else 'listening'
            results.append({
                'level':        level,
                'lesson':       lesson,
                'progress':     progress,
                'skill':        skill,
                'type':         first.get('type'),
                'category':     category,
                'status':       status,
                'unit_ids':     sorted(gdata['unit_ids']),
                'total_words':  total,
                'known_words':  known,
                'coverage':     round(coverage, 4),
                'coverage_pct': round(coverage * 100, 1),
                'matched_words': matched_words,
                'recent_matched_words': recent_matched_words,
                'newest_learned_at': newest_learned_at.isoformat() if newest_learned_at else None,
                'newest_learned_sort': newest_learned_at.timestamp() if newest_learned_at else 0,
                'recent_score': recent_score,
                'questions':    qs,
            })

        results = greedy_rank_recommendations(results)
        for item in results:
            item.pop('newest_learned_sort', None)
        return results

    except Exception as e:
        print(f"[WARN] get_recommended_practices failed: {e}")
        return []

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
        cur.execute("SELECT cn as word, pinyin, meaning_vn, meaning_en, audio_key, hsk_level as level FROM vocabulary WHERE hsk_level IS NOT NULL AND hsk_level != '' ORDER BY hsk_level, id")
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
