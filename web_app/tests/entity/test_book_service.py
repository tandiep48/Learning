import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.book import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeBook:
    def __init__(self, book_code="AML", name_en="A Month in Life", name_vn="Mot thang"):
        self.book_code = book_code
        self.name_en = name_en
        self.name_vn = name_vn


# ---------------------------------------------------------------------------
# list_books
# ---------------------------------------------------------------------------

def test_list_books_returns_dicts():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_all.return_value = [FakeBook("AML"), FakeBook("H1")]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        result = service.list_books()

    assert result == [
        {"book_code": "AML", "name_en": "A Month in Life", "name_vn": "Mot thang"},
        {"book_code": "H1", "name_en": "A Month in Life", "name_vn": "Mot thang"},
    ]
    session_local.remove.assert_called_once()


# ---------------------------------------------------------------------------
# get_book
# ---------------------------------------------------------------------------

def test_get_book_returns_dict_when_found():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_code.return_value = FakeBook()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        result = service.get_book("AML")

    assert result == {"book_code": "AML", "name_en": "A Month in Life", "name_vn": "Mot thang"}


def test_get_book_raises_404_when_missing():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_code.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        with pytest.raises(service.BookServiceError) as exc_info:
            service.get_book("MISSING")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# create_book
# ---------------------------------------------------------------------------

def test_create_book_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_code.return_value = None
    repo.create.return_value = FakeBook()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        result = service.create_book({"book_code": "AML", "name_en": "A Month in Life"})

    assert result["book_code"] == "AML"
    session.commit.assert_called_once()


def test_create_book_rejects_empty_book_code():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(service.BookServiceError):
            service.create_book({"book_code": "  "})


def test_create_book_rejects_duplicate():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_code.return_value = FakeBook()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        with pytest.raises(service.BookServiceError):
            service.create_book({"book_code": "AML"})

    session.rollback.assert_called_once()


def test_create_book_handles_integrity_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_code.return_value = None
    repo.create.side_effect = IntegrityError("stmt", {}, Exception("dup"))

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        with pytest.raises(service.BookServiceError) as exc_info:
            service.create_book({"book_code": "AML"})

    assert "already exists" in exc_info.value.message
    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# update_book
# ---------------------------------------------------------------------------

def test_update_book_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update.return_value = FakeBook(name_en="Updated")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        result = service.update_book("AML", {"name_en": "Updated"})

    assert result["name_en"] == "Updated"
    session.commit.assert_called_once()


def test_update_book_rejects_empty_payload():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(service.BookServiceError):
            service.update_book("AML", {})


def test_update_book_raises_404_when_missing():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        with pytest.raises(service.BookServiceError) as exc_info:
            service.update_book("MISSING", {"name_en": "X"})

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# delete_book
# ---------------------------------------------------------------------------

def test_delete_book_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.delete.return_value = True

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        result = service.delete_book("AML")

    assert "deleted" in result["message"]
    session.commit.assert_called_once()


def test_delete_book_raises_404_when_missing():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.delete.return_value = False

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "BookRepository", return_value=repo):
        with pytest.raises(service.BookServiceError) as exc_info:
            service.delete_book("MISSING")

    assert exc_info.value.status_code == 404
