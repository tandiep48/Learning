"""
entity/user_lesson_part_progress/entity.py
--------------------------------------------
SQLAlchemy ORM model for the `user_lesson_part_progress` table — tracks, per
user and passage/part, when the lesson trainer was completed and the score.
"""

from sqlalchemy import Column, BigInteger, String, SmallInteger, DateTime
from entity.database import Base


class UserLessonPartProgress(Base):
    __tablename__ = "user_lesson_part_progress"

    user_id = Column(BigInteger, primary_key=True)
    passage_id = Column(String, primary_key=True)
    lesson_trainer_completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    score_pct = Column(SmallInteger, nullable=True)
