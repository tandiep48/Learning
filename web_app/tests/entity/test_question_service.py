import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.question import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeQuestion:
    def __init__(self, **overrides):
        self.id = overrides.get("id", 1)
        self.level = overrides.get("level", 1)
        self.category = overrides.get("category", "practice")
        self.lesson = overrides.get("lesson", 2)
        self.no = overrides.get("no", 1)
        self.skill = overrides.get("skill", "reading")
        self.type = overrides.get("type", 1)
        self.content = overrides.get("content", "passage text")
        self.question = overrides.get("question", "What is...?")
        self.answer = overrides.get("answer", "A")
        self.audio_key = overrides.get("audio_key", None)
        self.image = overrides.get("image", None)
        self.options = overrides.get("options", {"A": True})
        self.progress = overrides.get("progress", "1")
        self.unit_id = overrides.get("unit_id", "")

    def to_dict(self):
        return {
            "id": self.id, "level": self.level, "category": self.category,
            "lesson": self.lesson, "no": self.no, "skill": self.skill,
            "type": self.type, "content": self.content, "question": self.question,
            "answer": self.answer, "audio_key": self.audio_key, "image": self.image,
            "options": self.options, "progress": self.progress, "unit_id": self.unit_id,
        }


# ---------------------------------------------------------------------------
# list_practice_lessons
# ---------------------------------------------------------------------------

def test_list_practice_lessons_stringifies_lesson_numbers():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.list_distinct_lessons.return_value = [1, 2, 3]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "QuestionRepository", return_value=repo):
        result = service.list_practice_lessons("practice", 1)

    assert result == ["1", "2", "3"]
    repo.list_distinct_lessons.assert_called_once_with("practice", 1)
    session_local.remove.assert_called_once()


# ---------------------------------------------------------------------------
# get_practice_questions
# ---------------------------------------------------------------------------

def test_get_practice_questions_serializes_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_category_level_lesson.return_value = [FakeQuestion(no=1), FakeQuestion(no=2)]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "QuestionRepository", return_value=repo):
        result = service.get_practice_questions("practice", 1, 2)

    assert [q["no"] for q in result] == [1, 2]
    repo.get_by_category_level_lesson.assert_called_once_with("practice", 1, 2)


def test_get_practice_questions_returns_empty_list_when_none_found():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_category_level_lesson.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "QuestionRepository", return_value=repo):
        assert service.get_practice_questions("practice", 1, 99) == []


# ---------------------------------------------------------------------------
# get_practice_progress_group
# ---------------------------------------------------------------------------

def test_get_practice_progress_group_serializes_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_progress_group.return_value = [FakeQuestion(progress="2")]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "QuestionRepository", return_value=repo):
        result = service.get_practice_progress_group("practice", 1, 2, "2")

    assert result == [FakeQuestion(progress="2").to_dict()]
    repo.get_by_progress_group.assert_called_once_with("practice", 1, 2, "2")


# ---------------------------------------------------------------------------
# get_practice_questions_multi
# ---------------------------------------------------------------------------

def test_get_practice_questions_multi_delegates_items_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_groups.return_value = [FakeQuestion(level=1, lesson=2, progress="1")]
    items = [{"level": 1, "lesson": 2, "progress": "1", "category": "practice"}]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "QuestionRepository", return_value=repo):
        result = service.get_practice_questions_multi(items)

    assert len(result) == 1
    repo.get_by_groups.assert_called_once_with(items)


def test_get_practice_questions_multi_returns_empty_list_for_no_items():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_groups.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "QuestionRepository", return_value=repo):
        assert service.get_practice_questions_multi([]) == []
