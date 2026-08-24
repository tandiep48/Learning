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

    def to_dict(self) -> dict:
        """Serialize the entity to a plain dict for JSON responses."""
        return {
            "cn": self.cn,
            "zh": self.zh,
            "total_strokes_cn": self.total_strokes_cn,
            "total_strokes_zh": self.total_strokes_zh,
            "strokes_cn": self.strokes_cn,
            "strokes_zh": self.strokes_zh,
            "word_length": self.word_length,
            "strokes_difficult_cn": float(self.strokes_difficult_cn) if self.strokes_difficult_cn is not None else None,
            "strokes_difficult_cn_norm": float(self.strokes_difficult_cn_norm) if self.strokes_difficult_cn_norm is not None else None,
            "strokes_difficult_zh": float(self.strokes_difficult_zh) if self.strokes_difficult_zh is not None else None,
            "strokes_difficult_zh_norm": float(self.strokes_difficult_zh_norm) if self.strokes_difficult_zh_norm is not None else None,
        }
