"""
entity/user_learning_state/entity.py
-------------------------------------
SQLAlchemy ORM model for the `user_learning_state` table — the user's current
(most recent) lesson passage, one row per user.
"""

from sqlalchemy import Column, BigInteger, String, DateTime
from entity.database import Base


class UserLearningState(Base):
    __tablename__ = "user_learning_state"

    user_id = Column(BigInteger, primary_key=True)
    current_passage_id = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
