"""
entity/user_saved_word/entity.py
---------------------------------
SQLAlchemy ORM model for the `user_saved_word` table — a user's personal word
list, one row per (user, passage, word) they saved.

Schema reference (schema.sql):
    user_id     BIGINT       -- FK → users(id)                    ON DELETE CASCADE
    passage_id  VARCHAR(100) -- FK → lesson_passages(passage_id)  ON DELETE CASCADE
    cn          VARCHAR(100) -- FK → vocabulary(cn)               ON DELETE CASCADE
    created_at  TIMESTAMPTZ
    PRIMARY KEY (user_id, passage_id, cn)
"""

from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, func
from entity.database import Base


class UserSavedWord(Base):
    __tablename__ = "user_saved_word"

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON responses."""
        return {
            "user_id": self.user_id,
            "passage_id": self.passage_id,
            "cn": self.cn,
        }

    def __repr__(self) -> str:
        return (
            f"<UserSavedWord user_id={self.user_id} "
            f"passage_id={self.passage_id!r} cn={self.cn!r}>"
        )
