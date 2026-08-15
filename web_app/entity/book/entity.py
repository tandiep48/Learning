"""
entity/book/entity.py
----------------------
SQLAlchemy ORM model for the `books` table (per-book metadata for the Books tab).

Columns:
    book_code  VARCHAR(20) PRIMARY KEY   -- e.g. "AML"
    name_en    VARCHAR(200)              -- localized book name
    name_vn    VARCHAR(200)
"""

from sqlalchemy import Column, String
from entity.database import Base


class Book(Base):
    __tablename__ = "books"

    book_code = Column(String(20), primary_key=True)
    name_en = Column(String(200), nullable=True)
    name_vn = Column(String(200), nullable=True)

    def name(self, lang: str) -> str:
        """Localized name, falling back to English then the code."""
        if lang == "vi":
            return self.name_vn or self.name_en or self.book_code
        return self.name_en or self.name_vn or self.book_code

    def __repr__(self) -> str:
        return f"<Book book_code={self.book_code!r}>"
