"""
entity/validation.py
----------------------
Generic, reusable payload validators shared by the admin CRUD `service.py`
modules.

Front-end forms already validate input before it is sent, but a request can
always bypass the browser (curl, a script, a compromised client), so every
field an admin endpoint writes to the database is re-validated here too —
defense in depth, not a replacement for the per-entity business rules
(uniqueness, format regexes, etc.) that stay in each entity's own service.py.

Every helper takes the caller's `<Entity>ServiceError` class as `error_cls`
so a validation failure raises the same exception type (and status code)
the rest of that entity's service already uses.
"""

from __future__ import annotations


def require_str(error_cls, field: str, value, max_len: int | None = None) -> str:
    """Non-empty, trimmed string. Raises if missing, wrong type, or too long."""
    if value is None or isinstance(value, bool) or not isinstance(value, str):
        raise error_cls(f"Field '{field}' is required and must be a string.")
    value = value.strip()
    if not value:
        raise error_cls(f"Field '{field}' is required.")
    if max_len is not None and len(value) > max_len:
        raise error_cls(f"Field '{field}' must be {max_len} characters or fewer.")
    return value


def optional_str(error_cls, field: str, value, max_len: int | None = None) -> str | None:
    """Trimmed string, or None. Raises if present but the wrong type or too long."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str):
        raise error_cls(f"Field '{field}' must be a string or null.")
    value = value.strip()
    if max_len is not None and len(value) > max_len:
        raise error_cls(f"Field '{field}' must be {max_len} characters or fewer.")
    return value or None


def require_int(error_cls, field: str, value) -> int:
    """Integer, rejecting bool (a subclass of int) and non-numeric strings."""
    if isinstance(value, bool) or value is None:
        raise error_cls(f"Field '{field}' must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise error_cls(f"Field '{field}' must be an integer.")


def optional_int(error_cls, field: str, value) -> int | None:
    if value in (None, ""):
        return None
    return require_int(error_cls, field, value)


def require_one_of(error_cls, field: str, value, allowed):
    if value not in allowed:
        choices = ", ".join(str(v) for v in sorted(allowed, key=str))
        raise error_cls(f"Field '{field}' must be one of: {choices}.")
    return value


def optional_one_of(error_cls, field: str, value, allowed) -> str | None:
    if value in (None, ""):
        return None
    return require_one_of(error_cls, field, value, allowed)


def optional_dict(error_cls, field: str, value) -> dict | None:
    """A JSON object, or None. Raises if present but not a dict (e.g. a string or list)."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise error_cls(f"Field '{field}' must be a JSON object or null.")
    return value


def optional_list(error_cls, field: str, value) -> list | None:
    """A JSON array, or None. Raises if present but not a list."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise error_cls(f"Field '{field}' must be an array or null.")
    return value
