"""
db/progress.py
---------------
Queries for a user's lesson progress and recent-learning state —
recent lesson, lesson-part completion, the lesson-picker progress summary,
and marking a passage's words mastered.
Extracted from the former monolithic db.py.
"""

import time
from datetime import datetime, timezone

from sqlalchemy import select, insert, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from entity.database import SessionLocal
from entity.passage.entity import LessonPassage
from entity.lesson_line.entity import LessonLine  # noqa: F401  (registers LessonPassage.lines mapper)
from entity.passage_vocabulary.entity import PassageVocabulary
from entity.record.entity import VocabRecord
from entity.user_lesson_part_progress.entity import UserLessonPartProgress
from entity.user_learning_state.entity import UserLearningState
from db.records import get_learned_words


def set_recent_learning(conn, user_id, passage_id):
    if not conn or not passage_id:
        return False
    session = SessionLocal()
    try:
        stmt = pg_insert(UserLearningState).values(
            user_id=user_id,
            current_passage_id=passage_id,
            updated_at=func.current_timestamp(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserLearningState.user_id],
            set_={
                "current_passage_id": stmt.excluded.current_passage_id,
                "updated_at": func.current_timestamp(),
            },
        )
        session.execute(stmt)
        session.commit()
        return True
    except Exception as e:
        print(f"⚠️ Database set_recent_learning failed: {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()


def get_recent_learning(conn, user_id):
    if not conn:
        return None
    session = SessionLocal()
    try:
        row = session.execute(
            select(UserLearningState.current_passage_id, UserLearningState.updated_at)
            .where(UserLearningState.user_id == user_id)
        ).first()
        if not row:
            return None
        return {"passage_id": row[0], "updated_at": row[1].isoformat() if row[1] else None}
    except Exception as e:
        print(f"⚠️ Database get_recent_learning failed: {e}")
        return None
    finally:
        SessionLocal.remove()


def mark_lesson_part_completed(conn, user_id, passage_id, completed=True, score_pct=None):
    """Record lesson-trainer progress for a part.
    - completed=True stamps lesson_trainer_completed_at (binary "done").
    - score_pct (0-100, from the master trainer) is kept as the highest value seen,
      so progress never decreases. Passing None leaves the existing score untouched.
    """
    if not conn or not passage_id:
        return False
    session = SessionLocal()
    try:
        tbl = UserLessonPartProgress
        stmt = pg_insert(tbl).values(
            user_id=user_id,
            passage_id=passage_id,
            lesson_trainer_completed_at=(func.current_timestamp() if completed else None),
            score_pct=score_pct,
            updated_at=func.current_timestamp(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[tbl.user_id, tbl.passage_id],
            set_={
                "lesson_trainer_completed_at": func.coalesce(
                    stmt.excluded.lesson_trainer_completed_at,
                    tbl.lesson_trainer_completed_at,
                ),
                "score_pct": func.greatest(
                    func.coalesce(tbl.score_pct, 0),
                    func.coalesce(stmt.excluded.score_pct, 0),
                ),
                "updated_at": func.current_timestamp(),
            },
        )
        session.execute(stmt)
        session.commit()
        return True
    except Exception as e:
        print(f"Database mark_lesson_part_completed failed: {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()


def get_lesson_picker_progress(conn, user_id, hsk_level):
    if not conn:
        return {"lessons": {}, "parts": {}}

    session = SessionLocal()
    try:
        mastered_words = set(get_learned_words(user_id))

        vocab_rows = session.execute(
            select(LessonPassage.passage_id, PassageVocabulary.cn)
            .select_from(LessonPassage)
            .outerjoin(PassageVocabulary, PassageVocabulary.passage_id == LessonPassage.passage_id)
            .where(LessonPassage.hsk_level == hsk_level)
            .order_by(LessonPassage.passage_id, PassageVocabulary.cn)
        ).all()

        completed_passages = set()
        part_scores = {}
        for pid, completed_at, score in session.execute(
            select(
                UserLessonPartProgress.passage_id,
                UserLessonPartProgress.lesson_trainer_completed_at,
                UserLessonPartProgress.score_pct,
            ).where(UserLessonPartProgress.user_id == user_id)
        ).all():
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
    finally:
        SessionLocal.remove()


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
    session = SessionLocal()
    try:
        words = [
            r[0]
            for r in session.execute(
                select(PassageVocabulary.cn).where(PassageVocabulary.passage_id == passage_id)
            ).all()
            if r[0]
        ]
        if not words:
            return 0

        already = set(get_learned_words(user_id))
        pending = [w for w in words if w not in already]
        if not pending:
            return 0

        session_id = int(time.time() * 1000)
        game_info = {"source": "lesson_trainer", "passage_id": passage_id}
        now = datetime.now(timezone.utc)  # one timestamp for the whole insert (like CURRENT_TIMESTAMP)
        rows = [
            {
                "user_id": user_id,
                "session_id": session_id,
                "mode": mode,
                "word": word,
                "round_num": 1,
                "is_correct": True,
                "game_info": game_info,
                "updated_at": now,
            }
            for word in pending
            for mode in ("typing", "listen", "meaning")
        ]
        session.execute(insert(VocabRecord), rows)
        session.commit()
        return len(pending)
    except Exception as e:
        print(f"Database mark_passage_words_mastered failed: {e}")
        session.rollback()
        return 0
    finally:
        SessionLocal.remove()
