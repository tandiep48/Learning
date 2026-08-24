"""
entity/book/repository.py
---------------------------
All database operations for the `books` table using SQLAlchemy ORM.
"""

from typing import Optional
from sqlalchemy.orm import Session

from entity.book.entity import Book


class BookRepository:
    """Encapsulates all CRUD operations for Book."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_all(self) -> list[Book]:
        """Return every book, ordered by book_code."""
        return self.session.query(Book).order_by(Book.book_code).all()

    def get_by_code(self, book_code: str) -> Optional[Book]:
        """Return a single Book, or None if not found."""
        return self.session.get(Book, book_code)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> Book:
        """
        Insert a new book.

        Args:
            data: Dict with keys "book_code" (required), "name_en", "name_vn".

        Raises:
            IntegrityError: if book_code already exists.
        """
        book = Book(
            book_code=data["book_code"],
            name_en=data.get("name_en"),
            name_vn=data.get("name_vn"),
        )
        self.session.add(book)
        self.session.flush()
        return book

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, book_code: str, data: dict) -> Optional[Book]:
        """Update an existing book's fields. Returns None if not found."""
        book = self.get_by_code(book_code)
        if not book:
            return None

        if "name_en" in data:
            book.name_en = data["name_en"]
        if "name_vn" in data:
            book.name_vn = data["name_vn"]

        self.session.flush()
        return book

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, book_code: str) -> bool:
        """Delete a book. Returns True if deleted, False if not found."""
        book = self.get_by_code(book_code)
        if not book:
            return False
        self.session.delete(book)
        self.session.flush()
        return True
