"""
repository/question_repository.py
-----------------------------------
All database operations for the `question_bank` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from typing import Optional
from sqlalchemy.orm import Session

from entity.question_entity import Question


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
