import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.user import service
from entity.user.service import UserServiceError


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeUser:
    def __init__(self, id=1, username="alice", email="alice@example.com", level=1):
        self.id = id
        self.username = username
        self.email = email
        self.level = level
        self.password = "hashed"
        self.avatar_path = None
        self.hanzi_font = None
        self.hanzi_script = None
        self.ui_language = None

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email, "level": self.level}

    def to_auth_dict(self):
        return {
            "id": self.id, "username": self.username, "email": self.email,
            "password": self.password, "level": self.level,
            "avatar_path": self.avatar_path, "hanzi_font": self.hanzi_font,
            "hanzi_script": self.hanzi_script, "ui_language": self.ui_language,
        }


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

def test_create_user_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_username.return_value = None
    repo.get_by_email.return_value = None
    repo.create.return_value = FakeUser()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        result = service.create_user({"username": "alice", "email": "alice@example.com", "password": "secret"})

    assert result["username"] == "alice"
    assert "password" not in result
    session.commit.assert_called_once()
    session_local.remove.assert_called_once()


def test_create_user_missing_password_raises_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(UserServiceError) as exc:
            service.create_user({"username": "alice", "email": "alice@example.com"})

    assert exc.value.status_code == 400
    session_local.assert_not_called()


def test_create_user_duplicate_username_raises_409():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_username.return_value = FakeUser()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        with pytest.raises(UserServiceError) as exc:
            service.create_user({"username": "alice", "email": "new@example.com", "password": "secret"})

    assert exc.value.status_code == 409
    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_user / delete_user
# ---------------------------------------------------------------------------

def test_get_user_not_found_raises_404():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_id.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        with pytest.raises(UserServiceError) as exc:
            service.get_user(999)

    assert exc.value.status_code == 404


def test_delete_user_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.delete.return_value = True

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        result = service.delete_user(1)

    assert "deleted" in result["message"]
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def test_get_user_auth_by_username_returns_password_hash():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_username.return_value = FakeUser()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        result = service.get_user_auth_by_username("alice")

    assert result["password"] == "hashed"


def test_get_user_auth_by_username_missing_returns_none():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_username.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        assert service.get_user_auth_by_username("ghost") is None


def test_username_or_email_exists_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.exists_by_username_or_email.return_value = True

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        assert service.username_or_email_exists("alice", "alice@example.com") is True

    repo.exists_by_username_or_email.assert_called_once_with("alice", "alice@example.com")


# ---------------------------------------------------------------------------
# HSK level progression
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,lesson_pct,word_pct,expected", [
    (1, 85, 0, True),
    (1, 50, 85, True),
    (1, 84, 84, False),
    (5, 75, 0, True),
    (6, 70, 0, True),
    (6, 69, 39, False),
])
def test_level_passes_bands(level, lesson_pct, word_pct, expected):
    assert service._level_passes(level, lesson_pct, word_pct) is expected


def test_recompute_user_level_advances_and_persists():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_level_progress_by_level.return_value = {
        1: {"lesson_total": 10, "lesson_done": 10, "word_total": 10, "word_done": 10},
        **{lvl: {"lesson_total": 0, "lesson_done": 0, "word_total": 0, "word_done": 0} for lvl in range(2, 7)},
    }
    repo.get_by_id.return_value = FakeUser(level=1)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo), \
         patch.object(service, "get_learned_words", return_value=set()):
        result = service.recompute_user_level(1)

    assert result == 2
    repo.set_level.assert_called_once_with(1, 2)
    session.commit.assert_called_once()


def test_recompute_user_level_never_decreases():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_level_progress_by_level.return_value = {
        lvl: {"lesson_total": 0, "lesson_done": 0, "word_total": 0, "word_done": 0} for lvl in range(1, 7)
    }
    repo.get_by_id.return_value = FakeUser(level=4)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo), \
         patch.object(service, "get_learned_words", return_value=set()):
        result = service.recompute_user_level(1)

    assert result == 4
    repo.set_level.assert_not_called()


# ---------------------------------------------------------------------------
# Profile settings
# ---------------------------------------------------------------------------

def test_get_user_hanzi_font_falls_back_to_default_when_unset():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_id.return_value = FakeUser()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        assert service.get_user_hanzi_font(1) == service.DEFAULT_HANZI_FONT


def test_update_user_password_hashes_via_update_setting():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update.return_value = FakeUser()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserRepository", return_value=repo):
        assert service.update_user_password(1, "already-hashed") is True

    repo.update.assert_called_once_with(1, {"password": "already-hashed"})
    session.commit.assert_called_once()
