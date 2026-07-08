"""
repository/user_repository.py
-------------------------------
All database operations for the `users` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
The service layer is responsible for hashing passwords before they reach here.
"""

from typing import Optional
from sqlalchemy.orm import Session

from entity.user_entity import User


class UserRepository:
    """Encapsulates all CRUD operations for the User entity."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """
        Return a paginated list of users and the total count.

        Args:
            page:      1-indexed page number.
            page_size: Items per page (max 100).
            search:    Optional case-insensitive match on username or email.

        Returns:
            (items, total_count)
        """
        query = self.session.query(User)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                User.username.ilike(pattern) | User.email.ilike(pattern)
            )

        total = query.count()
        items = (
            query.order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Return a single User by primary key, or None."""
        return self.session.get(User, user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        """Return a single User by username (unique), or None."""
        return (
            self.session.query(User)
            .filter(User.username == username)
            .first()
        )

    def get_by_email(self, email: str) -> Optional[User]:
        """Return a single User by email (unique), or None."""
        return (
            self.session.query(User)
            .filter(User.email == email)
            .first()
        )

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, data: dict) -> User:
        """
        Insert a new user.

        Args:
            data: Dict with keys "username", "email", "password" (already
                  hashed by the service layer) and optional "level".

        Returns:
            The newly created User (after flush).

        Raises:
            IntegrityError: if username or email already exists.
        """
        user = User(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            level=data.get("level", 1),
        )
        self.session.add(user)
        self.session.flush()  # flush to get the auto-generated id
        return user

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, user_id: int, data: dict) -> Optional[User]:
        """
        Update allowed fields on an existing user.

        Only keys present in `data` are changed. The service layer is
        responsible for hashing "password" before calling this.

        Args:
            user_id: Primary key of the user to update.
            data:    Dict of fields to update.

        Returns:
            The updated User, or None if not found.
        """
        user = self.get_by_id(user_id)
        if not user:
            return None

        updatable_fields = {"username", "email", "password", "level"}
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])

        self.session.flush()
        return user

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete(self, user_id: int) -> bool:
        """
        Delete a user by ID.

        Returns:
            True if deleted, False if not found.
        """
        user = self.get_by_id(user_id)
        if not user:
            return False
        self.session.delete(user)
        self.session.flush()
        return True
