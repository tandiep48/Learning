"""
entity/competition/entity.py
-----------------------------
SQLAlchemy ORM models for the multiplayer "Learn Together" (vocab competition)
feature. One file for the whole feature since the tables are tightly coupled:

    competition_rooms          — a lobby/room
    competition_room_members   — who is in a room
    competition_chat_messages  — room chat
    competition_sessions       — a running/finished round for a room
    competition_scores         — per-participant score for a session
    competition_vocab_answers  — one row per (participant, word, activity)
"""

from sqlalchemy import (
    Column, BigInteger, Integer, SmallInteger, String, Text, Boolean, DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB
from entity.database import Base


class CompetitionRoom(Base):
    __tablename__ = "competition_rooms"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    room_code = Column(String(12), nullable=False, unique=True)
    host_user_id = Column(BigInteger, nullable=False)
    category = Column(String(20), nullable=False, default="vocab")
    activity_type = Column(String(20), nullable=False, default="all")
    level = Column(SmallInteger, nullable=False)
    lesson = Column(Integer, nullable=True)
    progress = Column(String(30), nullable=True)
    passage_ids = Column(JSONB, nullable=False, default=list)
    word_count = Column(Integer, nullable=False, default=0)
    max_users = Column(SmallInteger, nullable=False, default=8)
    section_timeout_minutes = Column(SmallInteger, nullable=False, default=15)
    status = Column(String(30), nullable=False, default="waiting")
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class CompetitionRoomMember(Base):
    __tablename__ = "competition_room_members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    room_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    role = Column(String(20), nullable=False, default="participant")
    status = Column(String(30), nullable=False, default="online")
    joined_at = Column(DateTime(timezone=True))
    left_at = Column(DateTime(timezone=True))
    last_seen_at = Column(DateTime(timezone=True))


class CompetitionChatMessage(Base):
    __tablename__ = "competition_chat_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    room_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True))


class CompetitionSession(Base):
    __tablename__ = "competition_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    room_id = Column(BigInteger, nullable=False)
    status = Column(String(30), nullable=False, default="listening")
    current_section = Column(String(20), nullable=False, default="listening")
    section_started_at = Column(DateTime(timezone=True))
    section_ends_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    lesson_tasks = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True))


class CompetitionScore(Base):
    __tablename__ = "competition_scores"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    listening_points = Column(Integer, nullable=False, default=0)
    reading_points = Column(Integer, nullable=False, default=0)
    total_points = Column(Integer, nullable=False, default=0)
    total_response_time_ms = Column(Integer, nullable=False, default=0)
    finished_at = Column(DateTime(timezone=True))
    rank = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class CompetitionVocabAnswer(Base):
    __tablename__ = "competition_vocab_answers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    word = Column(Text, nullable=False)
    activity_type = Column(String(20), nullable=False)
    user_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=False)
    response_time_ms = Column(Integer, nullable=False, default=0)
    points = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime(timezone=True))
