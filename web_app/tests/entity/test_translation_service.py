import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.translation import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeTranslation:
    def __init__(self, translation_id, cn, vn, en):
        self.translation_id = translation_id
        self.cn = cn
        self.vn = vn
        self.en = en


def test_get_lesson_translations_builds_prefix_from_digits():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_translation_id_prefix.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "TranslationRepository", return_value=repo):
        service.get_lesson_translations("HSK1", "lesson 2")

    repo.get_by_translation_id_prefix.assert_called_once_with("H1_2_")
    session_local.remove.assert_called_once()


def test_get_lesson_translations_serializes_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_translation_id_prefix.return_value = [
        FakeTranslation("H1_2_1", "你好", "Xin chào", "Hello"),
        FakeTranslation("H1_2_2", "谢谢", "Cảm ơn", "Thank you"),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "TranslationRepository", return_value=repo):
        result = service.get_lesson_translations("1", "2")

    assert result == [
        {"translation_id": "H1_2_1", "cn": "你好", "vn": "Xin chào", "en": "Hello"},
        {"translation_id": "H1_2_2", "cn": "谢谢", "vn": "Cảm ơn", "en": "Thank you"},
    ]


def test_get_lesson_translations_returns_empty_list_when_hsk_level_missing():
    session, session_local = _mock_session()

    with patch.object(service, "SessionLocal", session_local):
        assert service.get_lesson_translations("", "2") == []
        assert service.get_lesson_translations(None, "2") == []

    session_local.assert_not_called()


def test_get_lesson_translations_returns_empty_list_when_lesson_missing():
    session, session_local = _mock_session()

    with patch.object(service, "SessionLocal", session_local):
        assert service.get_lesson_translations("HSK1", "") == []
        assert service.get_lesson_translations("HSK1", None) == []

    session_local.assert_not_called()
