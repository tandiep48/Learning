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
from entity.book.entity import Book
from entity.lesson_line.entity import LessonLine  # noqa: F401  (registers LessonPassage.lines mapper)
from entity.passage_vocabulary.entity import PassageVocabulary
from entity.record.entity import VocabRecord
from entity.user_lesson_part_progress.entity import UserLessonPartProgress
from entity.user_learning_state.entity import UserLearningState
from db.records import get_learned_words


def set_recent_learning(user_id, passage_id):
    if not passage_id:
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


def get_recent_learning(user_id):
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


def mark_lesson_part_completed(user_id, passage_id, completed=True, score_pct=None):
    """Record lesson-trainer progress for a part.
    - completed=True stamps lesson_trainer_completed_at (binary "done").
    - score_pct (0-100, from the master trainer) is kept as the highest value seen,
      so progress never decreases. Passing None leaves the existing score untouched.
    """
    if not passage_id:
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


def get_lesson_picker_progress(user_id, hsk_level):
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


def _lesson_sort_key(value):
    """Numeric-aware sort key so lesson/part '2' comes before '10' (not string order)."""
    s = str(value)
    return (0, int(s)) if s.isdigit() else (1, s)


def _pick_lang(en, vn, lang):
    """Localized text: Vietnamese for 'vi', else English; each falls back to the other."""
    if lang == "vi":
        return vn or en
    return en or vn


def get_books_summary(user_id, lang="en"):
    """One row per topic book (book_code) with localized name, cover URL and the user's
    completion counts. Books have no vocab, so this is passage/part based only."""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(LessonPassage.passage_id, LessonPassage.book_code)
            .where(LessonPassage.book_code.isnot(None))
        ).all()

        names = {
            code: _pick_lang(name_en, name_vn, lang)
            for code, name_en, name_vn in session.execute(
                select(Book.book_code, Book.name_en, Book.name_vn)
            ).all()
        }

        completed = {
            pid for (pid,) in session.execute(
                select(UserLessonPartProgress.passage_id).where(
                    UserLessonPartProgress.user_id == user_id,
                    UserLessonPartProgress.lesson_trainer_completed_at.isnot(None),
                )
            ).all()
        }

        books = {}
        for passage_id, code in rows:
            book = books.setdefault(code, {
                "book_code": code,
                "name": names.get(code) or code,
                "cover_url": f"/lesson-cover/{code}",
                "part_count": 0,
                "done_count": 0,
                "_lessons": set(),
            })
            id_parts = str(passage_id).split("_")
            book["_lessons"].add(id_parts[1] if len(id_parts) >= 2 else "Other")
            book["part_count"] += 1
            if passage_id in completed:
                book["done_count"] += 1

        result = []
        for book in books.values():
            book["lesson_count"] = len(book.pop("_lessons"))
            result.append(book)
        result.sort(key=lambda b: b["book_code"])
        return result
    finally:
        SessionLocal.remove()


def get_book_lessons(user_id, book_code, lang="en"):
    """Lessons → parts for one book, each lesson carrying its localized title and each part
    the user's completion/progress. Returns None if the book has no passages (unknown code)."""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(LessonPassage.passage_id, LessonPassage.title_en, LessonPassage.title_vn)
            .where(LessonPassage.book_code == book_code)
        ).all()
        if not rows:
            return None

        book = session.get(Book, book_code)
        book_name = _pick_lang(book.name_en, book.name_vn, lang) if book else book_code

        progress = {
            pid: (completed_at is not None, score or 0)
            for pid, completed_at, score in session.execute(
                select(
                    UserLessonPartProgress.passage_id,
                    UserLessonPartProgress.lesson_trainer_completed_at,
                    UserLessonPartProgress.score_pct,
                ).where(UserLessonPartProgress.user_id == user_id)
            ).all()
        }

        lessons = {}
        for passage_id, title_en, title_vn in rows:
            id_parts = str(passage_id).split("_")
            lesson_num = id_parts[1] if len(id_parts) >= 2 else "Other"
            part_num = id_parts[2] if len(id_parts) >= 3 else "1"
            done, score = progress.get(passage_id, (False, 0))
            lesson = lessons.setdefault(lesson_num, {"lesson": lesson_num, "title": None, "parts": []})
            # The title lives on the part-1 passage; take it whenever present.
            title = _pick_lang(title_en, title_vn, lang)
            if title and not lesson["title"]:
                lesson["title"] = title
            lesson["parts"].append({
                "passage_id": passage_id,
                "part": part_num,
                "completed": done,
                "progress_pct": max(100 if done else 0, score),
            })

        ordered = []
        for lesson_num in sorted(lessons, key=_lesson_sort_key):
            lesson = lessons[lesson_num]
            lesson["parts"].sort(key=lambda p: _lesson_sort_key(p["part"]))
            lesson["part_count"] = len(lesson["parts"])
            lesson["done_count"] = sum(1 for p in lesson["parts"] if p["completed"])
            ordered.append(lesson)

        return {"book_code": book_code, "book_name": book_name, "lessons": ordered}
    finally:
        SessionLocal.remove()


def mark_passage_words_mastered(user_id, passage_id):
    """
    Record that the user mastered every vocabulary word of a passage by completing its
    lesson-trainer part at 100%. Writes the same 3-mode (typing/listen/meaning), round-1,
    correct rows into vocab_records that the vocab trainer would, so every mastery consumer
    (recommend, profile, level, progress bars) picks it up with no query changes.
    Words already mastered are skipped so replays don't pile up duplicate records.
    Returns the count of newly mastered words.
    """
    if not passage_id:
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
