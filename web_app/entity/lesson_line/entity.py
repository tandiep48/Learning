"""
entity/lesson_line_entity.py
-----------------------------
SQLAlchemy ORM model for the `lesson_lines` table.

Schema (created by migrate_lessons.py):
    id              SERIAL PRIMARY KEY
    passage_id      VARCHAR(100) FK → lesson_passages(passage_id) ON DELETE CASCADE
    line_id         INT                    -- ordering within the passage
    speaker         VARCHAR(50)
    content         TEXT                   -- Chinese text of the line
    pinyin          TEXT
    audio_key       VARCHAR(100)
    translation_en  TEXT
    translation_vi  TEXT
    tokens          JSONB                  -- tokenised word list
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from entity.database import Base


class LessonLine(Base):
    __tablename__ = "lesson_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    passage_id = Column(
        String(100),
        ForeignKey("lesson_passages.passage_id", ondelete="CASCADE"),
        nullable=False,
    )
    line_id = Column(Integer, nullable=True)
    speaker = Column(String(50), nullable=True)
    content = Column(Text, nullable=True)
    pinyin = Column(Text, nullable=True)
    audio_key = Column(String(100), nullable=True)
    translation_en = Column(Text, nullable=True)
    translation_vi = Column(Text, nullable=True)
    tokens = Column(JSONB, nullable=True)

    # Back-reference to the parent passage
    passage = relationship("LessonPassage", back_populates="lines")

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON responses."""
        return {
            "id": self.id,
            "passage_id": self.passage_id,
            "line_id": self.line_id,
            "speaker": self.speaker,
            "content": self.content,
            "pinyin": self.pinyin,
            "audio_key": self.audio_key,
            "translation_en": self.translation_en,
            "translation_vi": self.translation_vi,
            "tokens": self.tokens if self.tokens is not None else [],
        }

    def __repr__(self) -> str:
        return (
            f"<LessonLine id={self.id} passage={self.passage_id!r} "
            f"line_id={self.line_id}>"
        )
