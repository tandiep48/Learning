"""
entity/support/service.py
-------------------------
Business logic for support tickets. Students only ever see their own tickets
(`owner_id` scoping); staff functions take no user scope. Every function opens
and closes its own session and returns plain dicts.
"""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from entity.database import SessionLocal
from entity.support.entity import SupportMessage, SupportTicket
from entity.user.entity import User


class SupportServiceError(Exception):
    """Raised for business-rule violations (404-level errors)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _page(query, page: int, page_size: int) -> dict:
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [t.to_dict() for t in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def _load(session: Session, ticket_id: int, owner_id: int | None) -> SupportTicket:
    """Fetch a ticket; a non-owner gets the same 404 as a missing ticket."""
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket or (owner_id is not None and ticket.user_id != owner_id):
        raise SupportServiceError(f"Ticket {ticket_id} not found.", 404)
    return ticket


def _with_messages(ticket: SupportTicket) -> dict:
    return {**ticket.to_dict(), "messages": [m.to_dict() for m in ticket.messages]}


def create_ticket(user_id: int, data: dict) -> dict:
    """Open a ticket with its first message (`data` is a validated TicketCreate dump)."""
    session = SessionLocal()
    try:
        ticket = SupportTicket(
            user_id=user_id,
            subject=data["subject"],
            item_type=data.get("item_type"),
            item_id=data.get("item_id"),
            page_url=data.get("page_url"),
        )
        ticket.messages.append(SupportMessage(sender_id=user_id, is_staff=False, body=data["body"]))
        session.add(ticket)
        session.commit()
        return _with_messages(ticket)
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def list_my_tickets(user_id: int, page: int = 1, page_size: int = 20) -> dict:
    session = SessionLocal()
    try:
        query = (
            session.query(SupportTicket)
            .filter(SupportTicket.user_id == user_id)
            .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
        )
        return _page(query, page, page_size)
    finally:
        SessionLocal.remove()


def list_tickets(
    page: int = 1, page_size: int = 20, status: str | None = None, search: str | None = None
) -> dict:
    """Staff inbox: newest activity first, optional status and subject/username search."""
    session = SessionLocal()
    try:
        query = session.query(SupportTicket)
        if status:
            query = query.filter(SupportTicket.status == status)
        if search:
            pattern = f"%{search}%"
            query = query.join(User, User.id == SupportTicket.user_id).filter(
                or_(SupportTicket.subject.ilike(pattern), User.username.ilike(pattern))
            )
        query = query.order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
        return _page(query, page, page_size)
    finally:
        SessionLocal.remove()


def get_ticket(ticket_id: int, owner_id: int | None = None) -> dict:
    """A ticket with its messages. Pass `owner_id` for the student view."""
    session = SessionLocal()
    try:
        return _with_messages(_load(session, ticket_id, owner_id))
    finally:
        SessionLocal.remove()


def add_message(ticket_id: int, sender_id: int, body: str, is_staff: bool) -> dict:
    """
    Append a reply. A student reply (owner-scoped) reopens a resolved ticket; a
    staff reply leaves the status alone.
    """
    session = SessionLocal()
    try:
        ticket = _load(session, ticket_id, None if is_staff else sender_id)
        message = SupportMessage(ticket_id=ticket.id, sender_id=sender_id, is_staff=is_staff, body=body)
        session.add(message)
        if not is_staff:
            ticket.status = "open"
        ticket.updated_at = func.now()
        session.commit()
        return message.to_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def update_ticket(ticket_id: int, changes: dict) -> dict:
    """Set `status` and/or `assignee_id` (0/None clears it); absent keys are untouched."""
    session = SessionLocal()
    try:
        ticket = _load(session, ticket_id, None)
        if changes.get("status"):
            ticket.status = changes["status"]
        if "assignee_id" in changes:
            assignee_id = changes["assignee_id"] or None
            if assignee_id and not session.get(User, assignee_id):
                raise SupportServiceError(f"User {assignee_id} not found.", 404)
            ticket.assignee_id = assignee_id
        ticket.updated_at = func.now()
        session.commit()
        session.refresh(ticket)
        return ticket.to_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()
