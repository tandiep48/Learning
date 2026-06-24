"""
entity/passage_entity.py
-------------------------
SQLAlchemy ORM model for the `lesson_passages` table.

After migration (migrate_lessons.py) the table has only two columns:
    passage_id  VARCHAR(100) PRIMARY KEY   -- e.g. "H1_1_1"
    hsk_level   VARCHAR(10)               -- e.g. "HSK1"

The lesson content lives in the related `lesson_lines` table
(see lesson_line_entity.py).
"""

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from entity.database import Base


class LessonPassage(Base):
    __tablename__ = "lesson_passages"

    passage_id = Column(String(100), primary_key=True)
    hsk_level = Column(String(10), nullable=True)

    # One passage → many lines (cascade delete mirrors DB ON DELETE CASCADE)
    lines = relationship(
        "LessonLine",
        back_populates="passage",
        cascade="all, delete-orphan",
        order_by="LessonLine.line_id",
        lazy="select",
    )

    def to_dict(self, include_lines: bool = False) -> dict:
        """Serialize to a plain dict for JSON responses."""
        data = {
            "passage_id": self.passage_id,
            "hsk_level": self.hsk_level,
        }
        if include_lines:
            data["lines"] = [line.to_dict() for line in self.lines]
        return data

    def __repr__(self) -> str:
        return f"<LessonPassage passage_id={self.passage_id!r} hsk={self.hsk_level!r}>"
