"""
entity/role/service.py
----------------------
Read-only lookups for roles and the permissions each role holds.
"""

from __future__ import annotations

from entity.database import SessionLocal
from entity.role.entity import Role, RolePermission

DEFAULT_ROLE = "student"
MANAGE_ACCESS = "manage:access"


def list_roles() -> list[str]:
    """Return every role name, sorted."""
    session = SessionLocal()
    try:
        return [name for (name,) in session.query(Role.name).order_by(Role.name).all()]
    finally:
        SessionLocal.remove()


def get_permissions(role: str | None) -> frozenset[str]:
    """Return the permission names granted to `role` (empty for an unknown/blank role)."""
    if not role:
        return frozenset()
    session = SessionLocal()
    try:
        rows = (
            session.query(RolePermission.permission)
            .filter(RolePermission.role == role)
            .all()
        )
        return frozenset(permission for (permission,) in rows)
    finally:
        SessionLocal.remove()
