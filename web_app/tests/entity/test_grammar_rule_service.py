import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.grammar_rule import service
from entity.grammar_rule.service import GrammarRuleServiceError


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


def test_get_grammar_for_lesson_builds_pattern_and_drops_missing_context():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_rules_for_lesson.return_value = [
        ("H1-2-1", 1, "vn text", "en text", None, None),
        ("H1-2-2", 4, "H1-2-1", "H1-2-1", {"note": "vi"}, {"note": "en"}),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "GrammarRuleRepository", return_value=repo):
        result = service.get_grammar_for_lesson(1, 2)

    repo.get_rules_for_lesson.assert_called_once_with("H1-2-%")
    assert result[0] == {
        "grammar_id": "H1-2-1", "type": 1,
        "vietnamese_content": "vn text", "english_content": "en text",
    }
    assert result[1]["vn_context"] == {"note": "vi"}
    assert result[1]["en_context"] == {"note": "en"}
    session_local.remove.assert_called_once()


def test_get_grammar_for_lesson_returns_empty_list_on_db_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_rules_for_lesson.side_effect = Exception("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "GrammarRuleRepository", return_value=repo):
        assert service.get_grammar_for_lesson(1, 2) == []


# ---------------------------------------------------------------------------
# create_grammar_rule / update_grammar_rule validation
# ---------------------------------------------------------------------------

class FakeRule:
    def __init__(self, id=1, grammar_id="H1-2-1", type=1, passage_number=1,
                 vietnamese_content="vn", english_content="en"):
        self.id = id
        self.grammar_id = grammar_id
        self.type = type
        self.passage_number = passage_number
        self.vietnamese_content = vietnamese_content
        self.english_content = english_content


def test_create_grammar_rule_rejects_missing_grammar_id_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(GrammarRuleServiceError):
            service.create_grammar_rule({"type": 1})

    session_local.assert_not_called()


def test_create_grammar_rule_rejects_out_of_range_type_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(GrammarRuleServiceError):
            service.create_grammar_rule({"grammar_id": "H1-2-1", "type": 99})

    session_local.assert_not_called()


def test_create_grammar_rule_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.create.return_value = FakeRule()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "GrammarRuleRepository", return_value=repo):
        result = service.create_grammar_rule({"grammar_id": "H1-2-1", "type": 1})

    assert result["grammar_id"] == "H1-2-1"
    session.commit.assert_called_once()


def test_update_grammar_rule_rejects_non_dict_content_field():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(GrammarRuleServiceError):
            service.update_grammar_rule(1, {"vietnamese_content": {"not": "a string"}})

    session_local.assert_not_called()
