"""
entity/learning_unit/entity.py
-------------------------------
SQLAlchemy ORM model for the `learning_units` table — maps a question bank
unit_id to each of its unique words. Used by the practice recommender to
measure how much of a group's vocabulary the user has mastered.
"""

from sqlalchemy import Column, Integer, String
from entity.database import Base


class LearningUnit(Base):
    __tablename__ = "learning_units"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(String(20), nullable=False)
    unique_word = Column(String(100), nullable=False)
