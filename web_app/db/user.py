"""
db/user.py
-----------
Queries for the `users` table — HSK level progression, profile/avatar,
hanzi font & script, UI language, password, and profile time summary.
Extracted from the former monolithic db.py.
"""

from db.records import get_learned_words


def _level_passes(level, lesson_pct, word_pct):
    """Per-band pass rule for HSK level progression (see recompute_user_level)."""
    if level in (1, 2):
        return lesson_pct >= 85 or (word_pct >= 85 and lesson_pct >= 50)
    if level in (3, 4):
        return lesson_pct >= 80 or (word_pct >= 80 and lesson_pct >= 50)
    if level == 5:
        return lesson_pct >= 75 or (word_pct >= 75 and lesson_pct >= 40)
    if level == 6:
        return lesson_pct >= 70 or (word_pct >= 70 and lesson_pct >= 40)
    return False


def recompute_user_level(conn, user_id):
    """
    Derive and (if higher) persist the user's HSK level from lesson-trainer progress.
    For each level compute lesson% (completed parts / total parts across ALL lessons at
    that level) and word% (mastered / total lesson words at that level), then apply the
    per-band pass rule in _level_passes. The user jumps to (highest passed level + 1),
    capped at HSK 6, and the level never decreases. Returns the resulting level.
    """
    if not conn:
        return None

    try:
        learned = get_learned_words(conn, user_id)
        parts = {}   # lvl -> (total_parts, done_parts)
        words = {}   # lvl -> (total_words, mastered_words)
        with conn.cursor() as cur:
            cur.execute(r"""
                SELECT (regexp_replace(split_part(lp.passage_id, '_', 1), '\D', '', 'g'))::int AS lvl,
                       COUNT(*)                AS total_parts,
                       COUNT(ulp.passage_id)   AS done_parts
                FROM lesson_passages lp
                LEFT JOIN user_lesson_part_progress ulp
                       ON ulp.passage_id = lp.passage_id
                      AND ulp.user_id = %s
                      AND ulp.lesson_trainer_completed_at IS NOT NULL
                WHERE lp.passage_id ~ '^H\d+_\d+_\d+$'
                GROUP BY 1
            """, (user_id,))
            for lvl, total, done in cur.fetchall():
                if lvl:
                    parts[lvl] = (total or 0, done or 0)

            cur.execute(r"""
                SELECT (regexp_replace(split_part(lp.passage_id, '_', 1), '\D', '', 'g'))::int AS lvl,
                       COUNT(DISTINCT pv.cn)                                     AS total_words,
                       COUNT(DISTINCT pv.cn) FILTER (WHERE pv.cn = ANY(%s::text[])) AS mastered_words
                FROM lesson_passages lp
                JOIN passage_vocabulary pv ON pv.passage_id = lp.passage_id
                WHERE lp.passage_id ~ '^H\d+_\d+_\d+$'
                GROUP BY 1
            """, (learned,))
            for lvl, total, mastered in cur.fetchall():
                if lvl:
                    words[lvl] = (total or 0, mastered or 0)

            cur.execute("SELECT level FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            current = int(row[0]) if row and row[0] else 1

        highest_passed = 0
        for lvl in range(1, 7):
            ptot, pdone = parts.get(lvl, (0, 0))
            wtot, wdone = words.get(lvl, (0, 0))
            lesson_pct = (pdone / ptot * 100) if ptot else 0
            word_pct = (wdone / wtot * 100) if wtot else 0
            if _level_passes(lvl, lesson_pct, word_pct):
                highest_passed = lvl

        target = min(6, highest_passed + 1) if highest_passed >= 1 else 1
        target = min(6, max(current, target))   # never decrease

        if target > current:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET level = %s WHERE id = %s", (target, user_id))
            conn.commit()
        return target
    except Exception as e:
        print(f"Database recompute_user_level failed: {e}")
        conn.rollback()
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

def get_user_hanzi_font(conn, user_id):
    if not conn:
        return "Noto Sans"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(hanzi_font, ''), 'Noto Sans') FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else "Noto Sans"
    except Exception as e:
        print(f"Database get_user_hanzi_font failed: {e}")
        conn.rollback()
        return "Noto Sans"

def update_user_hanzi_font(conn, user_id, hanzi_font):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET hanzi_font = %s WHERE id = %s", (hanzi_font, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database update_user_hanzi_font failed: {e}")
        conn.rollback()
        return False

def get_user_hanzi_script(conn, user_id):
    if not conn:
        return "simplified"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(hanzi_script, ''), 'simplified') FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else "simplified"
    except Exception as e:
        print(f"Database get_user_hanzi_script failed: {e}")
        conn.rollback()
        return "simplified"

def update_user_hanzi_script(conn, user_id, hanzi_script):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET hanzi_script = %s WHERE id = %s", (hanzi_script, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database update_user_hanzi_script failed: {e}")
        conn.rollback()
        return False

def get_user_ui_language(conn, user_id):
    if not conn:
        return "en"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(ui_language, ''), 'en') FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else "en"
    except Exception as e:
        print(f"Database get_user_ui_language failed: {e}")
        conn.rollback()
        return "en"

def update_user_ui_language(conn, user_id, ui_language):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET ui_language = %s WHERE id = %s", (ui_language, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database update_user_ui_language failed: {e}")
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
