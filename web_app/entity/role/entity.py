"""
entity/role/entity.py
---------------------
SQLAlchemy ORM models for role-based access control.

Schema reference (schema.sql):
    roles(name PK, description)
    permissions(name PK, description)
    role_permissions(role FK roles.name, permission FK permissions.name)
"""

from sqlalchemy import Column, ForeignKey, String
from entity.database import Base


class Role(Base):
    __tablename__ = "roles"

    name = Column(String(30), primary_key=True)
    description = Column(String(200), nullable=True)


class Permission(Base):
    __tablename__ = "permissions"

    name = Column(String(60), primary_key=True)
    description = Column(String(200), nullable=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role = Column(String(30), ForeignKey("roles.name"), primary_key=True)
    permission = Column(String(60), ForeignKey("permissions.name"), primary_key=True)
