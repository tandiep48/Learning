"""
entity/passage_vocabulary_entity.py
------------------------------------
SQLAlchemy ORM model for the `passage_vocabulary` join table.

Schema reference (schema.sql):
    passage_id  VARCHAR(100)   -- FK → lesson_passages(passage_id)  ON DELETE CASCADE
    cn          VARCHAR(100)   -- FK → vocabulary(cn)               ON DELETE CASCADE
    PRIMARY KEY (passage_id, cn)

Each row marks a vocabulary word (`cn`) as belonging to a passage, i.e. a
Chinese word that appears inside that passage's lines.
"""

from sqlalchemy import Column, String, ForeignKey
from entity.database import Base


class PassageVocabulary(Base):
    __tablename__ = "passage_vocabulary"

    passage_id = Column(
        String(100),
        ForeignKey("lesson_passages.passage_id", ondelete="CASCADE"),
        primary_key=True,
    )
    cn = Column(
        String(100),
        ForeignKey("vocabulary.cn", ondelete="CASCADE"),
        primary_key=True,
    )

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON responses."""
        return {
            "passage_id": self.passage_id,
            "cn": self.cn,
        }

    def __repr__(self) -> str:
        return f"<PassageVocabulary passage_id={self.passage_id!r} cn={self.cn!r}>"
