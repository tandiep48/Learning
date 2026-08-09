"""
entity/chinese_stroke_info/entity.py
-------------------------------------
SQLAlchemy ORM model for the `chinese_stroke_info` table — per-word stroke
counts and derived stroke-difficulty scores. Keyed by the Chinese word (`cn`).
"""

from sqlalchemy import Column, Integer, String, Text, Numeric
from entity.database import Base


class ChineseStrokeInfo(Base):
    __tablename__ = "chinese_stroke_info"

    cn = Column(String(255), primary_key=True)
    zh = Column(String(255), nullable=True)
    total_strokes_cn = Column(Integer, nullable=True)
    total_strokes_zh = Column(Integer, nullable=True)
    strokes_cn = Column(Text, nullable=True)
    strokes_zh = Column(Text, nullable=True)
    word_length = Column(Integer, nullable=True)
    strokes_difficult_cn = Column(Numeric, nullable=True)
    strokes_difficult_cn_norm = Column(Numeric, nullable=True)
    strokes_difficult_zh = Column(Numeric, nullable=True)
    strokes_difficult_zh_norm = Column(Numeric, nullable=True)
