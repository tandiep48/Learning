"""
entity/grammar_rule/entity.py
------------------------------
SQLAlchemy ORM model for the `grammar_rule` table — grammar rows for a lesson,
ordered by id; the caller splits the flat list into sections at each type=1 row.
"""

from sqlalchemy import Column, Integer, SmallInteger, String, Text
from entity.database import Base


class GrammarRule(Base):
    __tablename__ = "grammar_rule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grammar_id = Column(String, nullable=True)
    type = Column(SmallInteger, nullable=True)
    passage_number = Column(SmallInteger, nullable=True)
    vietnamese_content = Column(Text, nullable=True)
    english_content = Column(Text, nullable=True)
