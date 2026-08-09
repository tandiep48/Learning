"""
db/content.py
--------------
Read queries for lesson/passage content — passage summaries, lesson
translations, passage lines, course vocabulary, vocab lessons, passage
vocabulary and grammar.
Extracted from the former monolithic db.py.
"""


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

def get_lesson_translations(conn, hsk_level, lesson):
    """Return every translation row for one lesson, e.g. HSK1 + lesson 2 -> 'H1_2_%'.
    Ordered by the trailing index numerically so H1_2_10 follows H1_2_9, not H1_2_1."""
    if not conn:
        return []
    digits = "".join(ch for ch in str(hsk_level or "") if ch.isdigit())
    lesson_num = "".join(ch for ch in str(lesson or "") if ch.isdigit())
    if not digits or not lesson_num:
        return []
    prefix = f"H{digits}_{lesson_num}_"
    query = """
        SELECT translation_id, cn, vn, en
        FROM translation
        WHERE translation_id LIKE %s
        ORDER BY (split_part(translation_id, '_', 3))::int
    """
    with conn.cursor() as cur:
        cur.execute(query, (prefix + "%",))
        rows = cur.fetchall()
        return [{"translation_id": r[0], "cn": r[1], "vn": r[2], "en": r[3]} for r in rows]

def get_passage_content(conn, passage_id):
    if not conn: return None
    with conn.cursor() as cur:
        cur.execute("SELECT hsk_level FROM lesson_passages WHERE passage_id = %s", (passage_id,))
        row = cur.fetchone()
        if not row:
            return None
        hsk_level = row[0]
        
        cur.execute("""
            SELECT line_id, speaker, content, pinyin, audio_key, translation_en, translation_vi, tokens, flag
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
                "tokens": r[7] if r[7] else [],
                "flag": 1 if r[8] is None else r[8]
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
        cur.execute("SELECT cn as word, pinyin, meaning_vn, meaning_en, audio_key, hsk_level as level FROM vocabulary ORDER BY hsk_level, id")
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

def get_grammar_for_lesson(conn, hsk_level, lesson):
    """All grammar rules for a whole lesson (every part), ordered by insertion id.
    The caller splits the flat list into sections at each type=1 row."""
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
                WHERE r.grammar_id LIKE %s
                ORDER BY r.id ASC
            ''', (prefix,))
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
        print(f'[WARN] get_grammar_for_lesson failed: {e}')
        return []
