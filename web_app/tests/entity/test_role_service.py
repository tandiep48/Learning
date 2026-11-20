import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.role import service
from entity.user import service as user_service
from entity.user.service import UserServiceError


def _session(rows):
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = rows
    session.query.return_value.order_by.return_value.all.return_value = rows
    local = MagicMock(return_value=session)
    local.remove = MagicMock()
    return local


def test_get_permissions_returns_frozenset():
    with patch.object(service, "SessionLocal", _session([("user:read",), ("manage:access",)])):
        assert service.get_permissions("admin") == frozenset({"user:read", "manage:access"})


@pytest.mark.parametrize("role", [None, ""])
def test_get_permissions_blank_role_is_empty_without_db(role):
    with patch.object(service, "SessionLocal") as local:
        assert service.get_permissions(role) == frozenset()
    local.assert_not_called()


def test_list_roles():
    with patch.object(service, "SessionLocal", _session([("admin",), ("student",)])):
        assert service.list_roles() == ["admin", "student"]


def test_validate_role_accepts_known_role():
    with patch.object(user_service, "list_roles", return_value=["admin", "student"]):
        assert user_service._validate_role(" admin ") == "admin"


@pytest.mark.parametrize("role", ["superuser", "", None, 5])
def test_validate_role_rejects_bad_value(role):
    with patch.object(user_service, "list_roles", return_value=["admin", "student"]):
        with pytest.raises(UserServiceError):
            user_service._validate_role(role)
