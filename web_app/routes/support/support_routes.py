"""
routes/support/support_routes.py
--------------------------------
Student-facing support tickets. Every endpoint needs a signed-in user and only
ever touches that user's own tickets.

Prefix: /api/support

    POST /api/support/tickets                  -> open a ticket (subject, body, optional item)
    POST /api/support/tickets/query            -> my tickets (paginated)
    GET  /api/support/tickets/<id>             -> one ticket with its messages
    POST /api/support/tickets/<id>/messages    -> reply (reopens a resolved ticket)
"""

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from entity.support.schemas import MessageCreate, MyTicketsQuery, TicketCreate
from entity.support.service import (
    SupportServiceError,
    add_message,
    create_ticket,
    get_ticket,
    list_my_tickets,
)
from routes.validation import RequestValidationError, parse_body
from service.rate_limit import limiter, SENSITIVE_WRITE_LIMIT

support_bp = Blueprint("support", __name__, url_prefix="/api/support")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(exc: SupportServiceError):
    return jsonify({"success": False, "error": exc.message}), exc.status_code


@support_bp.route("/tickets", methods=["POST"])
@limiter.limit(SENSITIVE_WRITE_LIMIT)
@login_required
def create_ticket_endpoint():
    try:
        params = parse_body(TicketCreate)
    except RequestValidationError as exc:
        return exc.response()
    return _ok(create_ticket(int(current_user.id), params.model_dump()), 201)


@support_bp.route("/tickets/query", methods=["POST"])
@login_required
def list_my_tickets_endpoint():
    try:
        params = parse_body(MyTicketsQuery)
    except RequestValidationError as exc:
        return exc.response()
    return _ok(list_my_tickets(int(current_user.id), params.page, params.page_size))


@support_bp.route("/tickets/<int:ticket_id>", methods=["GET"])
@login_required
def get_ticket_endpoint(ticket_id: int):
    try:
        return _ok(get_ticket(ticket_id, owner_id=int(current_user.id)))
    except SupportServiceError as exc:
        return _error(exc)


@support_bp.route("/tickets/<int:ticket_id>/messages", methods=["POST"])
@limiter.limit(SENSITIVE_WRITE_LIMIT)
@login_required
def add_message_endpoint(ticket_id: int):
    try:
        params = parse_body(MessageCreate)
    except RequestValidationError as exc:
        return exc.response()
    try:
        return _ok(add_message(ticket_id, int(current_user.id), params.body, is_staff=False), 201)
    except SupportServiceError as exc:
        return _error(exc)
