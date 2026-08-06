"""
entity/record_entity.py
-------------------------
SQLAlchemy ORM models for the learner activity-record tables that feed the
dashboard statistics/charts:

    vocab_records    — vocab trainer answers
    lesson_records   — lesson trainer answers
    practice_record  — exercise / exam answers

Only the columns needed by the stats/chart queries are relied upon, but the
models mirror the live table columns so they can be reused later.
"""

from sqlalchemy import (
    Column,
    Integer,
    SmallInteger,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from entity.database import Base


class VocabRecord(Base):
    __tablename__ = "vocab_records"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(BigInteger)
    session_id = Column(BigInteger)
    mode = Column(String(50))
    word = Column(String(100))
    round_num = Column(Integer)
    game_info = Column(JSONB)
    user_answer = Column(Text)
    is_correct = Column(Boolean)
    response_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class LessonRecord(Base):
    __tablename__ = "lesson_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    session_id = Column(BigInteger)
    passage_id = Column(String(255))
    line_id = Column(Integer)
    mode = Column(SmallInteger)
    game_info = Column(Text)
    user_answer = Column(Text)
    is_correct = Column(Boolean)
    response_time_ms = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class PracticeRecord(Base):
    __tablename__ = "practice_record"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    session_id = Column(BigInteger)
    hsk_level = Column(Integer)
    lesson = Column(String(50))
    question_no = Column(Integer)
    skill = Column(String(50))
    question_type = Column(Integer)
    user_answer = Column(Text)
    is_correct = Column(Boolean)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    response_time_ms = Column(Integer)
    category = Column(String(50))
