import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.support import service
from entity.support.service import SupportServiceError


class FakeTicket:
    def __init__(self, user_id=7, status="resolved"):
        self.id = 5
        self.user_id = user_id
        self.status = status
        self.assignee_id = None
        self.updated_at = None
        self.messages = []

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "status": self.status, "assignee_id": self.assignee_id}


def _session(ticket=None):
    session = MagicMock()
    session.get.side_effect = lambda model, pk: ticket if model is service.SupportTicket else object()
    local = MagicMock(return_value=session)
    local.remove = MagicMock()
    return session, local


def test_student_reply_reopens_a_resolved_ticket():
    ticket = FakeTicket(status="resolved")
    session, local = _session(ticket)
    with patch.object(service, "SessionLocal", local):
        service.add_message(5, 7, "still wrong", is_staff=False)
    assert ticket.status == "open"
    session.commit.assert_called_once()


def test_staff_reply_keeps_status():
    ticket = FakeTicket(status="resolved")
    session, local = _session(ticket)
    with patch.object(service, "SessionLocal", local):
        service.add_message(5, 1, "fixed", is_staff=True)
    assert ticket.status == "resolved"


def test_student_cannot_reply_to_someone_elses_ticket():
    session, local = _session(FakeTicket(user_id=99))
    with patch.object(service, "SessionLocal", local):
        with pytest.raises(SupportServiceError) as err:
            service.add_message(5, 7, "hi", is_staff=False)
    assert err.value.status_code == 404
    session.rollback.assert_called_once()


def test_get_ticket_hides_other_users_ticket_from_a_student():
    _, local = _session(FakeTicket(user_id=99))
    with patch.object(service, "SessionLocal", local):
        with pytest.raises(SupportServiceError):
            service.get_ticket(5, owner_id=7)
        assert service.get_ticket(5)["user_id"] == 99


def test_update_ticket_sets_status_and_clears_assignee():
    ticket = FakeTicket(status="open")
    ticket.assignee_id = 3
    _, local = _session(ticket)
    with patch.object(service, "SessionLocal", local):
        result = service.update_ticket(5, {"status": "resolved", "assignee_id": 0})
    assert result["status"] == "resolved"
    assert result["assignee_id"] is None


def test_update_ticket_rejects_unknown_assignee():
    session, local = _session(FakeTicket())
    session.get.side_effect = lambda model, pk: FakeTicket() if model is service.SupportTicket else None
    with patch.object(service, "SessionLocal", local):
        with pytest.raises(SupportServiceError) as err:
            service.update_ticket(5, {"assignee_id": 404})
    assert err.value.status_code == 404


def test_update_ticket_missing_ticket_is_404():
    _, local = _session(None)
    with patch.object(service, "SessionLocal", local):
        with pytest.raises(SupportServiceError) as err:
            service.update_ticket(5, {"status": "open"})
    assert err.value.status_code == 404
