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

def insert_practice_progress(conn, user_id, session_id, hsk_level, lesson, question_no, skill, question_type, user_answer, is_correct):
    if not conn:
        return
        
    query = """
        INSERT INTO practice_record 
        (user_id, session_id, hsk_level, lesson, question_no, skill, question_type, user_answer, is_correct)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (
                user_id, str(session_id), hsk_level, str(lesson), question_no, skill, question_type, user_answer, is_correct
            ))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Database practice insert failed: {e}")
        conn.rollback()

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
        mastered = get_learned_words(conn, user_id)
        if not mastered:
            return []

        # 2. Compute coverage per unit_id — includes both practice (HP) and exam (HE) units
        coverage_sql = """
            SELECT
                lu.unit_id,
                COUNT(DISTINCT lu.unique_word)                                              AS total_words,
                COUNT(DISTINCT CASE WHEN lu.unique_word = ANY(%s) THEN lu.unique_word END)  AS known_words
            FROM learning_units lu
            WHERE lu.unit_id LIKE 'HP%%' OR lu.unit_id LIKE 'HE%%'
            GROUP BY lu.unit_id
            HAVING COUNT(DISTINCT lu.unique_word) > 0
        """
        with conn.cursor() as cur:
            cur.execute(coverage_sql, (list(mastered),))
            unit_coverage = {
                row[0]: {'total_words': row[1], 'known_words': row[2],
                         'coverage': row[2] / row[1]}
                for row in cur.fetchall()
                if row[1] > 0
            }

        # 3. Filter units meeting threshold
        ready_units = {uid for uid, d in unit_coverage.items() if d['coverage'] >= threshold}
        if not ready_units:
            return []

        # 4. Fetch all questions for ready units from question_bank (practice + exam)
        questions_sql = """
            SELECT level, lesson, progress, skill, type, unit_id,
                   no, content, question, answer, audio_key, image, options, category
            FROM question_bank
            WHERE category IN ('practice', 'exam') AND unit_id = ANY(%s)
            ORDER BY level, lesson, no
        """
        with conn.cursor() as cur:
            cur.execute(questions_sql, (list(ready_units),))
            cols = ['level', 'lesson', 'progress', 'skill', 'type', 'unit_id',
                    'no', 'content', 'question', 'answer', 'audio_key', 'image', 'options', 'category']
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        # 5. Group by (level, lesson, progress)
        from collections import defaultdict
        groups = defaultdict(lambda: {'questions': [], 'unit_ids': set()})
        for r in rows:
            key = (r['level'], r['lesson'], r['progress'])
            groups[key]['questions'].append(r)
            groups[key]['unit_ids'].add(r['unit_id'])

        # 6. Find 100%-complete latest sessions to exclude
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
                SELECT hsk_level::int, lesson::int FROM latest WHERE rn = 1 AND pct = 1.0
            """, (user_id,))
            completed_lessons = set((r[0], int(r[1])) for r in cur.fetchall())

        # 7. Build results — one per progress group
        results = []
        for (level, lesson, progress), gdata in groups.items():
            if (level, lesson) in completed_lessons:
                continue
            unit_ids = gdata['unit_ids']
            qs = gdata['questions']
            total = sum(unit_coverage[uid]['total_words'] for uid in unit_ids if uid in unit_coverage)
            known = sum(unit_coverage[uid]['known_words'] for uid in unit_ids if uid in unit_coverage)
            if total == 0:
                continue
            coverage = known / total
            if coverage < threshold:
                continue
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
                'category':     first.get('category', 'practice'),
                'unit_ids':     sorted(unit_ids),
                'total_words':  total,
                'known_words':  known,
                'coverage':     round(coverage, 4),
                'coverage_pct': round(coverage * 100, 1),
                'questions':    qs,
            })

        results.sort(key=lambda x: x['coverage'], reverse=True)
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

