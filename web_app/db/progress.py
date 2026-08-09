"""
db/progress.py
---------------
Queries for a user's lesson progress and recent-learning state —
recent lesson, lesson-part completion, the lesson-picker progress summary,
and marking a passage's words mastered.
Extracted from the former monolithic db.py.
"""

import json

from db.records import get_learned_words


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

def mark_lesson_part_completed(conn, user_id, passage_id, completed=True, score_pct=None):
    """Record lesson-trainer progress for a part.
    - completed=True stamps lesson_trainer_completed_at (binary "done").
    - score_pct (0-100, from the master trainer) is kept as the highest value seen,
      so progress never decreases. Passing None leaves the existing score untouched.
    """
    if not conn or not passage_id:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_lesson_part_progress
                    (user_id, passage_id, lesson_trainer_completed_at, score_pct, updated_at)
                VALUES (%s, %s,
                        CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                        %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, passage_id)
                DO UPDATE SET
                    lesson_trainer_completed_at = COALESCE(
                        EXCLUDED.lesson_trainer_completed_at,
                        user_lesson_part_progress.lesson_trainer_completed_at),
                    score_pct = GREATEST(
                        COALESCE(user_lesson_part_progress.score_pct, 0),
                        COALESCE(EXCLUDED.score_pct, 0)),
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, passage_id, bool(completed), score_pct))
        conn.commit()
        return True
    except Exception as e:
        print(f"Database mark_lesson_part_completed failed: {e}")
        conn.rollback()
        return False

def get_lesson_picker_progress(conn, user_id, hsk_level):
    if not conn:
        return {"lessons": {}, "parts": {}}

    try:
        mastered_words = set(get_learned_words(conn, user_id))

        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.passage_id, pv.cn
                FROM lesson_passages p
                LEFT JOIN passage_vocabulary pv ON pv.passage_id = p.passage_id
                WHERE p.hsk_level = %s
                ORDER BY p.passage_id, pv.cn
            """, (hsk_level,))
            vocab_rows = cur.fetchall()

            cur.execute("""
                SELECT passage_id, lesson_trainer_completed_at, score_pct
                FROM user_lesson_part_progress
                WHERE user_id = %s
            """, (user_id,))
            completed_passages = set()
            part_scores = {}
            for pid, completed_at, score in cur.fetchall():
                part_scores[pid] = score or 0
                if completed_at is not None:
                    completed_passages.add(pid)

        parts = {}
        lesson_words = {}
        lesson_passages = {}
        lesson_completed = {}

        for passage_id, word in vocab_rows:
            id_parts = str(passage_id or "").split("_")
            lesson_num = id_parts[1] if len(id_parts) >= 2 else "Other"

            part_progress = parts.setdefault(passage_id, {
                "passage_id": passage_id,
                "lesson": lesson_num,
                "total_words": 0,
                "learned_words": 0,
                "lesson_learned": 1 if passage_id in completed_passages else 0,
                "lesson_total": 1,
                # Effective progress: a completed part counts as 100%; otherwise the
                # master trainer's recorded score.
                "progress_pct": max(
                    100 if passage_id in completed_passages else 0,
                    part_scores.get(passage_id, 0),
                ),
                "_words": set(),
                "_learned_word_set": set(),
            })
            words_for_lesson = lesson_words.setdefault(lesson_num, set())
            passages_for_lesson = lesson_passages.setdefault(lesson_num, set())
            completed_for_lesson = lesson_completed.setdefault(lesson_num, set())

            passages_for_lesson.add(passage_id)
            if passage_id in completed_passages:
                completed_for_lesson.add(passage_id)

            if word:
                part_progress["_words"].add(word)
                words_for_lesson.add(word)
                if word in mastered_words:
                    part_progress["_learned_word_set"].add(word)

        for item in parts.values():
            item["total_words"] = len(item.pop("_words", set()))
            item["learned_words"] = len(item.pop("_learned_word_set", set()))

        lessons = {}
        for lesson_num, words in lesson_words.items():
            passages = lesson_passages.get(lesson_num, set())
            completed = lesson_completed.get(lesson_num, set())
            part_pcts = [parts[pid]["progress_pct"] for pid in passages if pid in parts]
            avg_pct = round(sum(part_pcts) / len(part_pcts)) if part_pcts else 0
            lessons[lesson_num] = {
                "lesson": lesson_num,
                "total_words": len(words),
                "learned_words": len(words.intersection(mastered_words)),
                "lesson_learned": len(completed),
                "lesson_total": len(passages),
                # Lesson progress = average of its parts' effective progress.
                "progress_pct": avg_pct,
            }

        return {"lessons": lessons, "parts": parts}
    except Exception as e:
        print(f"Database get_lesson_picker_progress failed: {e}")
        return {"lessons": {}, "parts": {}}


def mark_passage_words_mastered(conn, user_id, passage_id):
    """
    Record that the user mastered every vocabulary word of a passage by completing its
    lesson-trainer part at 100%. Writes the same 3-mode (typing/listen/meaning), round-1,
    correct rows into vocab_records that the vocab trainer would, so every mastery consumer
    (recommend, profile, level, progress bars) picks it up with no query changes.
    Words already mastered are skipped so replays don't pile up duplicate records.
    Returns the count of newly mastered words.
    """
    if not conn or not passage_id:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cn FROM passage_vocabulary WHERE passage_id = %s", (passage_id,))
            words = [r[0] for r in cur.fetchall() if r[0]]
        if not words:
            return 0

        already = set(get_learned_words(conn, user_id))
        pending = [w for w in words if w not in already]
        if not pending:
            return 0

        import time
        session_id = int(time.time() * 1000)
        game_info = json.dumps({"source": "lesson_trainer", "passage_id": passage_id},
                               ensure_ascii=False)
        rows = [
            (user_id, session_id, mode, word, game_info)
            for word in pending
            for mode in ('typing', 'listen', 'meaning')
        ]
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO vocab_records
                    (user_id, session_id, mode, word, round_num, is_correct,
                     game_info, updated_at)
                VALUES (%s, %s, %s, %s, 1, true, %s::jsonb, CURRENT_TIMESTAMP)
            """, rows)
        conn.commit()
        return len(pending)
    except Exception as e:
        print(f"Database mark_passage_words_mastered failed: {e}")
        conn.rollback()
        return 0
