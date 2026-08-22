"""
entity/user_entity.py
-----------------------
SQLAlchemy ORM model for the `users` table.

Schema reference (schema.sql):
    id        BIGSERIAL PRIMARY KEY
    username  VARCHAR(50)  NOT NULL UNIQUE
    email     VARCHAR(50)  NOT NULL UNIQUE
    password  VARCHAR(255) NOT NULL          -- werkzeug password hash
    level     SMALLINT     DEFAULT 1

Note: `to_dict()` never exposes the password hash.
"""

from sqlalchemy import Column, BigInteger, SmallInteger, String, Text
from entity.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(50), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    level = Column(SmallInteger, nullable=True, default=1)
    # Profile / preferences
    avatar_path = Column(Text, nullable=True)
    hanzi_font = Column(Text, nullable=True)
    hanzi_script = Column(Text, nullable=True)
    ui_language = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON responses (password excluded)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "level": self.level,
        }

    def to_auth_dict(self) -> dict:
        """Serialize including the password hash, for Flask-Login internal use only."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "password": self.password,
            "level": self.level,
            "avatar_path": self.avatar_path,
            "hanzi_font": self.hanzi_font,
            "hanzi_script": self.hanzi_script,
            "ui_language": self.ui_language,
        }

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} level={self.level!r}>"
