"""
entity/passage_entity.py
-------------------------
SQLAlchemy ORM model for the `lesson_passages` table.

Columns:
    passage_id  VARCHAR(100) PRIMARY KEY   -- e.g. "H1_1_1" or "AML_1_1"
    hsk_level   VARCHAR(10)                -- e.g. "HSK1"; NULL for book lessons
    book_code   VARCHAR(20)                -- e.g. "AML" for topic books; NULL for HSK

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
    # Set for topic "book" lessons (e.g. "AML"); NULL for regular HSK passages.
    book_code = Column(String(20), nullable=True)

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
            "book_code": self.book_code,
        }
        if include_lines:
            data["lines"] = [line.to_dict() for line in self.lines]
        return data

    def __repr__(self) -> str:
        return f"<LessonPassage passage_id={self.passage_id!r} hsk={self.hsk_level!r}>"
