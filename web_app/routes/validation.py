"""
routes/validation.py
---------------------
HTTP-layer helper for validating a JSON request body against a Pydantic v2
model and returning the project's standard error envelope on failure.

This complements entity/validation.py (the in-house field helpers used inside
the service layer): this module lives at the route boundary, turns a raw request
body into a typed, validated model, and maps schema failures to a 422 response
in the { success, error, details } shape the Next.js client already reads.

Usage:

    from routes.validation import parse_body, RequestValidationError

    @bp.route("/query", methods=["POST"])
    def query():
        try:
            params = parse_body(VocabQuery)
        except RequestValidationError as exc:
            return exc.response()
        ...
"""

from __future__ import annotations

from typing import Type, TypeVar

from flask import jsonify, request
from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)


class RequestValidationError(Exception):
    """A request body that failed schema validation. Maps to HTTP 422."""

    def __init__(self, message: str, details: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []

    def response(self):
        return (
            jsonify({"success": False, "error": self.message, "details": self.details}),
            422,
        )


def _format(exc: ValidationError) -> tuple[str, list[dict]]:
    """Turn Pydantic's error list into per-field details plus a one-line summary."""
    details = [
        {
            "field": ".".join(str(part) for part in err["loc"]) or "body",
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    summary = "; ".join(f"{d['field']}: {d['message']}" for d in details) or "Invalid request body."
    return summary, details


def parse_body(model_cls: Type[M]) -> M:
    """
    Validate the JSON request body into `model_cls`.

    Raises:
        RequestValidationError: if the body is not a JSON object, or fails the
        model's schema. Call `.response()` on it for the 422 Flask response.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise RequestValidationError("Request body must be a JSON object.")
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        message, details = _format(exc)
        raise RequestValidationError(message, details)
