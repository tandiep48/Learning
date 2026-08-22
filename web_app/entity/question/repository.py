"""
repository/question_repository.py
-----------------------------------
All database operations for the `question_bank` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from typing import Optional
from sqlalchemy import select, distinct, and_, or_
from sqlalchemy.orm import Session

from entity.question.entity import Question


class QuestionRepository:
    """Encapsulates all CRUD operations for the Question entity."""

    # Columns a caller is allowed to set on create / update.
    WRITABLE_FIELDS = {
        "level", "category", "lesson", "no", "skill", "type",
        "content", "question", "answer", "audio_key", "image",
        "options", "progress", "unit_id",
    }

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        level: Optional[int] = None,
        lesson: Optional[int] = None,
        skill: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Question], int]:
        """
        Return a paginated list of questions and the total count.

        Optional filters: category, level, lesson, skill, and a free-text
        `search` over the content / question columns.

        Returns:
            (items, total_count)
        """
        query = self.session.query(Question)
        if category:
            query = query.filter(Question.category == category)
        if level is not None:
            query = query.filter(Question.level == level)
        if lesson is not None:
            query = query.filter(Question.lesson == lesson)
        if skill:
            query = query.filter(Question.skill == skill)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                Question.content.ilike(pattern) | Question.question.ilike(pattern)
            )

        total = query.count()
        items = (
            query.order_by(
                Question.category, Question.level, Question.lesson, Question.no
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, question_id: int) -> Optional[Question]:
        """Return a single Question by primary key, or None."""
        return self.session.get(Question, question_id)

    def get_by_unique(
        self, category: str, level: int, lesson: int, no: int
    ) -> Optional[Question]:
        """Return the Question matching the (category, level, lesson, no) unique key."""
        return (
            self.session.query(Question)
            .filter(
                Question.category == category,
                Question.level == level,
                Question.lesson == lesson,
                Question.no == no,
            )
            .first()
        )

    # ------------------------------------------------------------------
    # READ — practice/exam trainer lookups
    # ------------------------------------------------------------------

    def list_distinct_lessons(self, category: str, level: int) -> list:
        """Distinct lesson numbers available for a practice/exam level."""
        rows = self.session.execute(
            select(distinct(Question.lesson))
            .where(Question.category == category, Question.level == level)
            .order_by(Question.lesson)
        ).all()
        return [r[0] for r in rows]

    def get_by_category_level_lesson(self, category: str, level: int, lesson) -> list[Question]:
        """All questions for one (category, level, lesson), ordered by question no."""
        return (
            self.session.execute(
                select(Question)
                .where(Question.category == category, Question.level == level, Question.lesson == lesson)
                .order_by(Question.no)
            )
            .scalars()
            .all()
        )

    def get_by_progress_group(self, category: str, level: int, lesson, progress) -> list[Question]:
        """All questions for one (category, level, lesson, progress) group, ordered by no."""
        return (
            self.session.execute(
                select(Question)
                .where(
                    Question.category == category, Question.level == level,
                    Question.lesson == lesson, Question.progress == progress,
                )
                .order_by(Question.no)
            )
            .scalars()
            .all()
        )

    def get_by_groups(self, groups: list[dict]) -> list[Question]:
        """
        Questions for several (category, level, lesson, progress) groups at once.
        `groups` is a list of dicts with those keys; ordered by level, lesson, progress, no.
        """
        conds = [
            and_(
                Question.category == g.get("category", "practice"),
                Question.level == g["level"],
                Question.lesson == g["lesson"],
                Question.progress == g["progress"],
            )
            for g in groups
        ]
        if not conds:
            return []
        return (
            self.session.execute(
                select(Question)
                .where(or_(*conds))
                .order_by(Question.level, Question.lesson, Question.progress, Question.no)
            )
            .scalars()
            .all()
        )

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> Question:
        """
        Insert a new question. Only WRITABLE_FIELDS present in `data` are used.

        Raises:
            IntegrityError: if the (category, level, lesson, no) key is duplicated.
        """
        values = {k: data[k] for k in self.WRITABLE_FIELDS if k in data}
        question = Question(**values)
        self.session.add(question)
        self.session.flush()  # flush to get the auto-generated id
        return question

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, question_id: int, data: dict) -> Optional[Question]:
        """
        Update allowed fields on an existing question.

        Only keys present in `data` (and in WRITABLE_FIELDS) are changed.

        Returns:
            The updated Question, or None if not found.
        """
        question = self.get_by_id(question_id)
        if not question:
            return None

        for field in self.WRITABLE_FIELDS:
            if field in data:
                setattr(question, field, data[field])

        self.session.flush()
        return question

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, question_id: int) -> bool:
        """
        Delete a question by ID.

        Returns:
            True if deleted, False if not found.
        """
        question = self.get_by_id(question_id)
        if not question:
            return False
        self.session.delete(question)
        self.session.flush()
        return True
