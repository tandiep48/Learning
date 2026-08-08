"""
entity/grammar_context/entity.py
---------------------------------
SQLAlchemy ORM model for the `grammar_context` table — extra JSON context
attached to certain grammar rows (joined when grammar_rule.type = 4).
"""

from sqlalchemy import Column, Integer, String, JSON
from entity.database import Base


class GrammarContext(Base):
    __tablename__ = "grammar_context"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grammar_id = Column(String, nullable=True)
    content_json = Column(JSON, nullable=True)
