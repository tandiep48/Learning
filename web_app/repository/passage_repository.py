"""
repository/passage_repository.py
----------------------------------
All database operations for `lesson_passages` and `lesson_lines`
using SQLAlchemy.

Design note:
  - `LessonPassage` is the aggregate root; `LessonLine` rows are always
    managed through their parent passage.
  - When a passage is deleted, its lines are removed automatically
    (cascade="all, delete-orphan" on the relationship).
"""

from typing import Optional
from sqlalchemy.orm import Session

from entity.passage_entity import LessonPassage
from entity.lesson_line_entity import LessonLine


class PassageRepository:
    """Encapsulates all CRUD operations for LessonPassage + LessonLine."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        hsk_level: Optional[str] = None,
    ) -> tuple[list[LessonPassage], int]:
        """
        Return a paginated list of passages (without lines) and total count.

        Args:
            page:      1-indexed page number.
            page_size: Items per page (max 100).
            hsk_level: Optional filter (e.g. "HSK1").

        Returns:
            (items, total_count)
        """
        query = self.session.query(LessonPassage)
        if hsk_level:
            query = query.filter(LessonPassage.hsk_level == hsk_level)

        total = query.count()
        items = (
            query.order_by(LessonPassage.hsk_level, LessonPassage.passage_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, passage_id: str) -> Optional[LessonPassage]:
        """
        Return a single LessonPassage with its lines eagerly loaded,
        or None if not found.
        """
        return self.session.get(LessonPassage, passage_id)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> LessonPassage:
        """
        Insert a new passage and (optionally) its lines.

        Args:
            data: Dict with keys:
                  - "passage_id"  (required, str)
                  - "hsk_level"   (optional, str)
                  - "lines"       (optional, list of line dicts)

        Returns:
            The newly created LessonPassage.

        Raises:
            IntegrityError: if passage_id already exists.
        """
        passage = LessonPassage(
            passage_id=data["passage_id"],
            hsk_level=data.get("hsk_level"),
        )
        self.session.add(passage)
        self.session.flush()  # ensure passage_id is persisted before lines

        for line_data in data.get("lines", []):
            line = LessonLine(
                passage_id=passage.passage_id,
                line_id=line_data.get("line_id"),
                speaker=line_data.get("speaker"),
                content=line_data.get("content"),
                pinyin=line_data.get("pinyin"),
                audio_key=line_data.get("audio_key"),
                translation_en=line_data.get("translation_en"),
                translation_vi=line_data.get("translation_vi"),
                tokens=line_data.get("tokens"),
            )
            self.session.add(line)

        self.session.flush()
        return passage

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, passage_id: str, data: dict) -> Optional[LessonPassage]:
        """
        Update a passage and optionally replace all its lines.

        If "lines" is present in `data`, the existing lines are deleted and
        replaced with the new set.  If "lines" is absent, lines are untouched.

        Args:
            passage_id: Primary key of the passage to update.
            data:       Dict of fields to update.

        Returns:
            The updated LessonPassage, or None if not found.
        """
        passage = self.get_by_id(passage_id)
        if not passage:
            return None

        if "hsk_level" in data:
            passage.hsk_level = data["hsk_level"]

        if "lines" in data:
            # Replace lines: delete existing then re-insert
            (
                self.session.query(LessonLine)
                .filter(LessonLine.passage_id == passage_id)
                .delete(synchronize_session="fetch")
            )
            for line_data in data["lines"]:
                line = LessonLine(
                    passage_id=passage_id,
                    line_id=line_data.get("line_id"),
                    speaker=line_data.get("speaker"),
                    content=line_data.get("content"),
                    pinyin=line_data.get("pinyin"),
                    audio_key=line_data.get("audio_key"),
                    translation_en=line_data.get("translation_en"),
                    translation_vi=line_data.get("translation_vi"),
                    tokens=line_data.get("tokens"),
                )
                self.session.add(line)

        self.session.flush()
        # Expire to reload relationship after potential line replacement
        self.session.expire(passage)
        return self.session.get(LessonPassage, passage_id)

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, passage_id: str) -> bool:
        """
        Delete a passage and all its lines (via cascade).

        Returns:
            True if deleted, False if not found.
        """
        passage = self.get_by_id(passage_id)
        if not passage:
            return False
        self.session.delete(passage)
        self.session.flush()
        return True
