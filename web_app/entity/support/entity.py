"""
entity/support/entity.py
------------------------
SQLAlchemy ORM models for support tickets and their messages.

Schema reference (schema.sql): support_tickets, support_messages.
"""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from entity.database import Base
from entity.user.entity import User  # noqa: F401  (registers the users table the FKs point at)


def _iso(value):
    return value.isoformat() if value else None


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    subject = Column(String(200), nullable=False)
    item_type = Column(String(30), nullable=True)
    item_id = Column(String(100), nullable=True)
    page_url = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="open")
    assignee_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    author = relationship("User", foreign_keys=[user_id], lazy="joined")
    assignee = relationship("User", foreign_keys=[assignee_id], lazy="joined")
    messages = relationship(
        "SupportMessage", order_by="SupportMessage.id", lazy="select", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.author.username if self.author else None,
            "subject": self.subject,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "page_url": self.page_url,
            "status": self.status,
            "assignee_id": self.assignee_id,
            "assignee_name": self.assignee.username if self.assignee else None,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("support_tickets.id"), nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    is_staff = Column(Boolean, nullable=False, default=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    sender = relationship("User", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender.username if self.sender else None,
            "is_staff": self.is_staff,
            "body": self.body,
            "created_at": _iso(self.created_at),
        }
