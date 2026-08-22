"""
repository/user_repository.py
-------------------------------
All database operations for the `users` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
The service layer is responsible for hashing passwords before they reach here.
"""

from typing import Optional

from sqlalchemy import and_, cast, distinct, func, Integer
from sqlalchemy.orm import Session

from entity.user.entity import User
from entity.passage.entity import LessonPassage
from entity.lesson_line.entity import LessonLine  # noqa: F401  (registers the mapper LessonPassage.lines references)
from entity.passage_vocabulary.entity import PassageVocabulary
from entity.user_lesson_part_progress.entity import UserLessonPartProgress
from entity.record.entity import VocabRecord, LessonRecord, PracticeRecord


class UserRepository:
    """Encapsulates all CRUD operations for the User entity."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """
        Return a paginated list of users and the total count.

        Args:
            page:      1-indexed page number.
            page_size: Items per page (max 100).
            search:    Optional case-insensitive match on username or email.

        Returns:
            (items, total_count)
        """
        query = self.session.query(User)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                User.username.ilike(pattern) | User.email.ilike(pattern)
            )

        total = query.count()
        items = (
            query.order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Return a single User by primary key, or None."""
        return self.session.get(User, user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        """Return a single User by username (unique), or None."""
        return (
            self.session.query(User)
            .filter(User.username == username)
            .first()
        )

    def get_by_email(self, email: str) -> Optional[User]:
        """Return a single User by email (unique), or None."""
        return (
            self.session.query(User)
            .filter(User.email == email)
            .first()
        )

    def exists_by_username_or_email(self, username: str, email: str) -> bool:
        """Return True if a user with this username or email already exists."""
        return (
            self.session.query(User.id)
            .filter((User.username == username) | (User.email == email))
            .first()
            is not None
        )

    def get_level_progress_by_level(self, user_id: int, learned_words: set) -> dict:
        """
        Return, per HSK level, the lesson-trainer completion and vocab-mastery
        progress needed to decide whether the user has passed that level.

        Returns:
            {level: {"lesson_total": int, "lesson_done": int,
                      "word_total": int, "word_done": int}}
        """
        lvl = cast(
            func.regexp_replace(
                func.split_part(LessonPassage.passage_id, "_", 1), r"\D", "", "g"
            ),
            Integer,
        ).label("lvl")
        is_lesson_passage = LessonPassage.passage_id.op("~")(r"^H\d+_\d+_\d+$")

        parts_by_level = {}
        q_parts = (
            self.session.query(
                lvl,
                func.count().label("total_parts"),
                func.count(UserLessonPartProgress.passage_id).label("done_parts"),
            )
            .select_from(LessonPassage)
            .outerjoin(
                UserLessonPartProgress,
                and_(
                    UserLessonPartProgress.passage_id == LessonPassage.passage_id,
                    UserLessonPartProgress.user_id == user_id,
                    UserLessonPartProgress.lesson_trainer_completed_at.isnot(None),
                ),
            )
            .filter(is_lesson_passage)
            .group_by(lvl)
        )
        for row in q_parts.all():
            if row.lvl:
                parts_by_level[row.lvl] = (row.total_parts or 0, row.done_parts or 0)

        words_by_level = {}
        q_words = (
            self.session.query(
                lvl,
                func.count(distinct(PassageVocabulary.cn)).label("total_words"),
                func.count(distinct(PassageVocabulary.cn))
                .filter(PassageVocabulary.cn.in_(learned_words))
                .label("mastered_words"),
            )
            .select_from(LessonPassage)
            .join(
                PassageVocabulary,
                PassageVocabulary.passage_id == LessonPassage.passage_id,
            )
            .filter(is_lesson_passage)
            .group_by(lvl)
        )
        for row in q_words.all():
            if row.lvl:
                words_by_level[row.lvl] = (row.total_words or 0, row.mastered_words or 0)

        progress = {}
        for level in range(1, 7):
            lesson_total, lesson_done = parts_by_level.get(level, (0, 0))
            word_total, word_done = words_by_level.get(level, (0, 0))
            progress[level] = {
                "lesson_total": lesson_total,
                "lesson_done": lesson_done,
                "word_total": word_total,
                "word_done": word_done,
            }
        return progress

    def set_level(self, user_id: int, level: int) -> None:
        """Persist a new HSK level for the user."""
        user = self.get_by_id(user_id)
        if user:
            user.level = level
            self.session.flush()

    def get_profile_summary(self, user_id: int) -> dict:
        """
        Aggregate per-mode/skill time spent by the user across the vocab,
        lesson, and practice/exam activity-record tables.
        """
        def _mode_time(model):
            return (
                self.session.query(
                    model.mode,
                    func.coalesce(func.sum(model.response_time_ms), 0),
                )
                .filter(model.user_id == user_id, model.response_time_ms.isnot(None))
                .group_by(model.mode)
                .order_by(model.mode)
                .all()
            )

        vocab_rows = _mode_time(VocabRecord)
        lesson_rows = _mode_time(LessonRecord)

        category = func.coalesce(PracticeRecord.category, "practice").label("category")
        skill = func.coalesce(PracticeRecord.skill, "unknown").label("skill")
        practice_rows = (
            self.session.query(
                category,
                skill,
                func.coalesce(func.sum(PracticeRecord.response_time_ms), 0),
            )
            .filter(PracticeRecord.user_id == user_id, PracticeRecord.response_time_ms.isnot(None))
            .group_by(category, skill)
            .order_by(category, skill)
            .all()
        )

        return {
            "vocab_mode_time_ms": [(row[0], int(row[1] or 0)) for row in vocab_rows],
            "lesson_mode_time_ms": [(row[0], int(row[1] or 0)) for row in lesson_rows],
            "practice_skill_time_ms": [
                (row[0], row[1], int(row[2] or 0)) for row in practice_rows
            ],
        }

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> User:
        """
        Insert a new user.

        Args:
            data: Dict with keys "username", "email", "password" (already
                  hashed by the service layer) and optional "level".

        Returns:
            The newly created User (after flush).

        Raises:
            IntegrityError: if username or email already exists.
        """
        user = User(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            level=data.get("level", 1),
        )
        self.session.add(user)
        self.session.flush()  # flush to get the auto-generated id
        return user

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, user_id: int, data: dict) -> Optional[User]:
        """
        Update allowed fields on an existing user.

        Only keys present in `data` are changed. The service layer is
        responsible for hashing "password" before calling this.

        Args:
            user_id: Primary key of the user to update.
            data:    Dict of fields to update.

        Returns:
            The updated User, or None if not found.
        """
        user = self.get_by_id(user_id)
        if not user:
            return None

        updatable_fields = {
            "username", "email", "password", "level",
            "avatar_path", "hanzi_font", "hanzi_script", "ui_language",
        }
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])

        self.session.flush()
        return user

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, user_id: int) -> bool:
        """
        Delete a user by ID.

        Returns:
            True if deleted, False if not found.
        """
        user = self.get_by_id(user_id)
        if not user:
            return False
        self.session.delete(user)
        self.session.flush()
        return True
