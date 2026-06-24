"""
entity/vocabulary_entity.py
----------------------------
SQLAlchemy ORM model for the `vocabulary` table.

Schema reference (schema.sql):
    id          SERIAL PRIMARY KEY
    cn          VARCHAR(100) NOT NULL UNIQUE    -- Chinese word
    pinyin      VARCHAR(100)
    meaning_en  TEXT
    meaning_vn  TEXT
    audio_key   VARCHAR(100)
    hsk_level   VARCHAR(10)                    -- e.g. "HSK1"
    source      VARCHAR(50)
"""

from sqlalchemy import Column, Integer, String, Text
from entity.database import Base


class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cn = Column(String(100), nullable=False, unique=True)
    pinyin = Column(String(100), nullable=True)
    meaning_en = Column(Text, nullable=True)
    meaning_vn = Column(Text, nullable=True)
    audio_key = Column(String(100), nullable=True)
    hsk_level = Column(String(10), nullable=True)
    source = Column(String(50), nullable=True)

    def to_dict(self) -> dict:
        """Serialize the entity to a plain dict for JSON responses."""
        return {
            "id": self.id,
            "cn": self.cn,
            "pinyin": self.pinyin,
            "meaning_en": self.meaning_en,
            "meaning_vn": self.meaning_vn,
            "audio_key": self.audio_key,
            "hsk_level": self.hsk_level,
            "source": self.source,
        }

    def __repr__(self) -> str:
        return f"<Vocabulary id={self.id} cn={self.cn!r} hsk={self.hsk_level!r}>"
