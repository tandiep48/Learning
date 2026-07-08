"""
entity/question_entity.py
--------------------------
SQLAlchemy ORM model for the `question_bank` table.

Schema reference (schema.sql):
    id        SERIAL PRIMARY KEY
    level     SMALLINT NOT NULL
    category  question_category NOT NULL      -- enum: 'practice' | 'exam'
    lesson    INTEGER  NOT NULL
    no        INTEGER  NOT NULL
    skill     question_skill                  -- enum: 'listening' | 'reading' (nullable)
    type      SMALLINT NOT NULL
    content   TEXT
    question  TEXT
    answer    VARCHAR(50)
    audio_key TEXT
    image     VARCHAR(255)
    options   JSONB
    progress  VARCHAR(30) NOT NULL
    unit_id   VARCHAR(20) NOT NULL DEFAULT ''

Unique: (category, level, lesson, no)
"""

from sqlalchemy import Column, Integer, SmallInteger, String, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB
from entity.database import Base

# Map to the existing PostgreSQL enum types (do NOT let SQLAlchemy create them).
QUESTION_CATEGORY = Enum(
    "practice", "exam", name="question_category", create_type=False
)
QUESTION_SKILL = Enum(
    "listening", "reading", name="question_skill", create_type=False
)


class Question(Base):
    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(SmallInteger, nullable=False)
    category = Column(QUESTION_CATEGORY, nullable=False)
    lesson = Column(Integer, nullable=False)
    no = Column(Integer, nullable=False)
    skill = Column(QUESTION_SKILL, nullable=True)
    type = Column(SmallInteger, nullable=False)
    content = Column(Text, nullable=True)
    question = Column(Text, nullable=True)
    answer = Column(String(50), nullable=True)
    audio_key = Column(Text, nullable=True)
    image = Column(String(255), nullable=True)
    options = Column(JSONB, nullable=True)
    progress = Column(String(30), nullable=False)
    unit_id = Column(String(20), nullable=False, default="")

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON responses."""
        return {
            "id": self.id,
            "level": self.level,
            "category": self.category,
            "lesson": self.lesson,
            "no": self.no,
            "skill": self.skill,
            "type": self.type,
            "content": self.content,
            "question": self.question,
            "answer": self.answer,
            "audio_key": self.audio_key,
            "image": self.image,
            "options": self.options,
            "progress": self.progress,
            "unit_id": self.unit_id,
        }

    def __repr__(self) -> str:
        return (
            f"<Question id={self.id} category={self.category!r} "
            f"level={self.level} lesson={self.lesson} no={self.no}>"
        )
