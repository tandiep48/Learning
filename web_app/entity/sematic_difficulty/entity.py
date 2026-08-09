"""
entity/sematic_difficulty/entity.py
------------------------------------
SQLAlchemy ORM model for the `sematic_diffculty` table — per-word semantic
difficulty score. `word_id` references vocabulary(id).

NOTE: the table/column names are misspelled in the live database
(`sematic_diffculty` / `sematic_difficulty`); the ORM keeps them verbatim.
"""

from sqlalchemy import Column, Integer, Text, Numeric
from entity.database import Base


class SemanticDifficulty(Base):
    __tablename__ = "sematic_diffculty"

    word_id = Column(Integer, primary_key=True)
    sematic_difficulty = Column(Numeric, nullable=True)
    tags = Column(Text, nullable=True)
