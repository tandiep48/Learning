"""
entity/progress/repository.py
-------------------------------
All database queries and mutations for a user's lesson progress and
recent-learning state using SQLAlchemy ORM — recent lesson, lesson-part
completion, the lesson-picker/book browsing reads, and the vocab-mastery
write-back triggered by completing a lesson part.

No raw SQL strings — all queries go through the ORM session. Session
lifecycle (commit/rollback/remove) is owned by the service layer.
"""

from sqlalchemy import select, insert, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from entity.passage.entity import LessonPassage
from entity.book.entity import Book
from entity.lesson_line.entity import LessonLine  # noqa: F401  (registers LessonPassage.lines mapper)
from entity.passage_vocabulary.entity import PassageVocabulary
from entity.record.entity import VocabRecord
from entity.user_lesson_part_progress.entity import UserLessonPartProgress
from entity.user_learning_state.entity import UserLearningState


class ProgressRepository:
    """Encapsulates all queries/mutations for lesson progress and recent-learning state."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Recent learning (user_learning_state)
    # ------------------------------------------------------------------

    def upsert_recent_learning(self, user_id, passage_id):
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
        self.session.execute(stmt)

    def get_recent_learning_row(self, user_id):
        return self.session.execute(
            select(UserLearningState.current_passage_id, UserLearningState.updated_at)
            .where(UserLearningState.user_id == user_id)
        ).first()

    # ------------------------------------------------------------------
    # Lesson-part progress (user_lesson_part_progress)
    # ------------------------------------------------------------------

    def upsert_lesson_part_progress(self, user_id, passage_id, completed, score_pct):
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
        self.session.execute(stmt)

    def get_user_lesson_part_progress(self, user_id):
        """(passage_id, lesson_trainer_completed_at, score_pct) rows for every part the
        user has touched."""
        return self.session.execute(
            select(
                UserLessonPartProgress.passage_id,
                UserLessonPartProgress.lesson_trainer_completed_at,
                UserLessonPartProgress.score_pct,
            ).where(UserLessonPartProgress.user_id == user_id)
        ).all()

    def get_completed_passage_ids(self, user_id):
        return {
            pid for (pid,) in self.session.execute(
                select(UserLessonPartProgress.passage_id).where(
                    UserLessonPartProgress.user_id == user_id,
                    UserLessonPartProgress.lesson_trainer_completed_at.isnot(None),
                )
            ).all()
        }

    # ------------------------------------------------------------------
    # Lesson/book browsing (lesson_passage, books, passage_vocabulary)
    # ------------------------------------------------------------------

    def get_passage_vocab_rows(self, hsk_level):
        """(passage_id, cn) rows for every passage/word pair at a given HSK level."""
        return self.session.execute(
            select(LessonPassage.passage_id, PassageVocabulary.cn)
            .select_from(LessonPassage)
            .outerjoin(PassageVocabulary, PassageVocabulary.passage_id == LessonPassage.passage_id)
            .where(LessonPassage.hsk_level == hsk_level)
            .order_by(LessonPassage.passage_id, PassageVocabulary.cn)
        ).all()

    def get_book_passage_rows(self):
        """(passage_id, book_code) rows for every passage that belongs to a topic book."""
        return self.session.execute(
            select(LessonPassage.passage_id, LessonPassage.book_code)
            .where(LessonPassage.book_code.isnot(None))
        ).all()

    def get_book_names(self):
        return self.session.execute(
            select(Book.book_code, Book.name_en, Book.name_vn)
        ).all()

    def get_book_passages_with_titles(self, book_code):
        return self.session.execute(
            select(LessonPassage.passage_id, LessonPassage.title_en, LessonPassage.title_vn)
            .where(LessonPassage.book_code == book_code)
        ).all()

    def get_book(self, book_code):
        return self.session.get(Book, book_code)

    # ------------------------------------------------------------------
    # Vocab-mastery write-back (passage_vocabulary -> vocab_records)
    # ------------------------------------------------------------------

    def get_passage_vocab_words(self, passage_id):
        return [
            r[0]
            for r in self.session.execute(
                select(PassageVocabulary.cn).where(PassageVocabulary.passage_id == passage_id)
            ).all()
            if r[0]
        ]

    def insert_vocab_mastery_records(self, rows):
        if not rows:
            return
        self.session.execute(insert(VocabRecord), rows)  # multi-row insert
