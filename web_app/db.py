import psycopg2

# --- DATABASE CONFIG ---
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "chinese" # Please update with actual database name
DB_USER = "postgres" # Please update with actual user
DB_PASS = "admin" # Please update with actual password

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

def get_learned_words(conn):
    """
    Returns a list of words that have been fully learned 
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
            cur.execute(query)
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_learned_words): {e}")
        return []

def get_unlearned_words_from_db(conn):
    """
    Returns a list of words from the history that have NOT been fully learned 
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
            cur.execute(query)
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_unlearned_words_from_db): {e}")
        return []

def get_unsure_words_from_db(conn):
    """
    Returns a list of unsure words that the user has learned but takes a longer time to answer.
    """
    if not conn:
        return []

    query = """
    WITH learned_words AS (
        SELECT word
        FROM vocab_records 
        WHERE is_correct = true
        GROUP BY word
        HAVING COUNT(*) >= 3
    ),
    stats AS (
        SELECT a.mode,
               AVG(a.response_time_ms) AS avg_rt,
               NULLIF(STDDEV(a.response_time_ms), 0) AS std_rt
        FROM vocab_records a
        JOIN learned_words b ON a.word = b.word
        GROUP BY a.mode
    )
    SELECT a.word
    FROM vocab_records a
    JOIN learned_words b ON a.word = b.word
    JOIN stats s ON a.mode = s.mode
    WHERE s.std_rt IS NOT NULL AND (a.response_time_ms - s.avg_rt) / s.std_rt > 1.0
    GROUP BY a.word
    ORDER BY MAX((a.response_time_ms - s.avg_rt) / s.std_rt) DESC;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_unsure_words_from_db): {e}")
        return []

def get_hard_semantic_learned_words(conn):
    """
    Returns a list of learned words but difficult in semantic.
    """
    if not conn:
        return []

    query = """
    WITH learned_words AS (
        SELECT word
        FROM vocab_records 
        WHERE is_correct IS TRUE
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
            cur.execute(query)
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_semantic_learned_words): {e}")
        return []

def get_hard_stroke_learned_words(conn):
    """
    Returns a list of learned words but difficult in strokes.
    """
    if not conn:
        return []

    query = """
    WITH learned_words AS (
        SELECT word
        FROM vocab_records 
        WHERE is_correct IS TRUE
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
            cur.execute(query)
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_stroke_learned_words): {e}")
        return []


def get_passages_summary(conn, hsk_level=None):
    if not conn: return []
    query = "SELECT passage_id, hsk_level, jsonb_array_length(content->'lines') as line_count FROM lesson_passages"
    params = ()
    if hsk_level:
        query += " WHERE hsk_level = %s"
        params = (hsk_level,)
    query += " ORDER BY passage_id"
    
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [{"passage_id": r[0], "hsk_level": r[1], "line_count": r[2]} for r in rows]

def get_passage_content(conn, passage_id):
    if not conn: return None
    with conn.cursor() as cur:
        cur.execute("SELECT hsk_level, content FROM lesson_passages WHERE passage_id = %s", (passage_id,))
        row = cur.fetchone()
        if row:
            content = row[1]
            content['hsk_level'] = row[0]
            return content
        return None

def get_vocab_by_source(conn, source):
    import pandas as pd
    if not conn: return pd.DataFrame()
    with conn.cursor() as cur:
        cur.execute("SELECT cn as word, pinyin, meaning_vn, meaning_en, audio_key, hsk_level as level FROM vocabulary WHERE source = %s", (source,))
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=['word', 'pinyin', 'meaning_vn', 'meaning_en', 'audio_key', 'level'])
        return df

def get_all_vn_meanings(conn):
    if not conn: return []
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT meaning_vn FROM vocabulary WHERE meaning_vn IS NOT NULL AND meaning_vn != ''")
        rows = cur.fetchall()
        return [r[0] for r in rows]
