"""
routes/support/support_admin_routes.py
--------------------------------------
Staff inbox for support tickets, guarded by support:read / support:write
(see routes.auth.permissions).

Prefix: /api/admin/support

    POST /api/admin/support/query              -> inbox (page, page_size, status, search)
    GET  /api/admin/support/<id>               -> ticket with messages
    POST /api/admin/support/<id>/messages      -> staff reply
    PUT  /api/admin/support/<id>               -> { status?, assignee_id? }
"""

from flask import Blueprint, jsonify
from flask_login import current_user

from entity.support.schemas import MessageCreate, TicketQuery, TicketUpdate
from entity.support.service import (
    SupportServiceError,
    add_message,
    get_ticket,
    list_tickets,
    update_ticket,
)
from routes.auth.permissions import guard_admin_blueprint
from routes.validation import RequestValidationError, parse_body

support_admin_bp = Blueprint("support_admin", __name__, url_prefix="/api/admin/support")
guard_admin_blueprint(support_admin_bp, "support")


def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def _error(exc: SupportServiceError):
    return jsonify({"success": False, "error": exc.message}), exc.status_code


@support_admin_bp.route("/query", methods=["POST"])
def query_tickets_endpoint():
    try:
        params = parse_body(TicketQuery)
    except RequestValidationError as exc:
        return exc.response()
    return _ok(list_tickets(params.page, params.page_size, params.status, params.search))


@support_admin_bp.route("/<int:ticket_id>", methods=["GET"])
def get_ticket_endpoint(ticket_id: int):
    try:
        return _ok(get_ticket(ticket_id))
    except SupportServiceError as exc:
        return _error(exc)


@support_admin_bp.route("/<int:ticket_id>/messages", methods=["POST"])
def reply_endpoint(ticket_id: int):
    try:
        params = parse_body(MessageCreate)
    except RequestValidationError as exc:
        return exc.response()
    try:
        return _ok(add_message(ticket_id, int(current_user.id), params.body, is_staff=True), 201)
    except SupportServiceError as exc:
        return _error(exc)


@support_admin_bp.route("/<int:ticket_id>", methods=["PUT"])
def update_ticket_endpoint(ticket_id: int):
    try:
        params = parse_body(TicketUpdate)
    except RequestValidationError as exc:
        return exc.response()
    try:
        return _ok(update_ticket(ticket_id, params.model_dump(include=params.model_fields_set)))
    except SupportServiceError as exc:
        return _error(exc)
