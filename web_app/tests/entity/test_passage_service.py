import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.passage import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeLine:
    def __init__(self, line_id, content, translation_en="Hello", translation_vi="Xin chào",
                 tokens=None, flag=None):
        self.line_id = line_id
        self.speaker = "A"
        self.content = content
        self.pinyin = "ni3 hao3"
        self.audio_key = "a.mp3"
        self.translation_en = translation_en
        self.translation_vi = translation_vi
        self.tokens = tokens
        self.flag = flag


class FakePassage:
    def __init__(self, passage_id="H1_1_1", hsk_level="HSK1", book_code=None, lines=None):
        self.passage_id = passage_id
        self.hsk_level = hsk_level
        self.book_code = book_code
        self.lines = lines or []


# ---------------------------------------------------------------------------
# get_passages_summary
# ---------------------------------------------------------------------------

def test_get_passages_summary_picks_title_by_lang():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_summary.return_value = [
        ("H1_1_1", "HSK1", 3, "Greetings", "Chào hỏi"),
        ("H1_1_2", "HSK1", 2, None, "Gia đình"),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "PassageRepository", return_value=repo):
        result_en = service.get_passages_summary("HSK1", lang="en")

    assert result_en == [
        {"passage_id": "H1_1_1", "hsk_level": "HSK1", "line_count": 3, "title": "Greetings"},
        {"passage_id": "H1_1_2", "hsk_level": "HSK1", "line_count": 2, "title": "Gia đình"},
    ]
    repo.get_summary.assert_called_once_with("HSK1")
    session_local.remove.assert_called_once()


def test_get_passages_summary_vi_falls_back_to_en_title():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_summary.return_value = [("H1_1_2", "HSK1", 2, "Family", None)]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "PassageRepository", return_value=repo):
        result = service.get_passages_summary(lang="vi")

    assert result[0]["title"] == "Family"


# ---------------------------------------------------------------------------
# get_passage_content
# ---------------------------------------------------------------------------

def test_get_passage_content_returns_none_when_not_found():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_id.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "PassageRepository", return_value=repo):
        assert service.get_passage_content("missing") is None


def test_get_passage_content_shapes_lines():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_id.return_value = FakePassage(lines=[
        FakeLine(1, "你好", tokens=["你好"], flag=None),
        FakeLine(2, "再见", tokens=None, flag=0),
    ])

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "PassageRepository", return_value=repo):
        result = service.get_passage_content("H1_1_1")

    assert result["passage_id"] == "H1_1_1"
    assert result["lines"][0] == {
        "line_id": 1, "speaker": "A", "content": "你好", "pinyin": "ni3 hao3",
        "audio_key": "a.mp3", "translations": {"en": "Hello", "vi": "Xin chào"},
        "tokens": ["你好"], "flag": 1,
    }
    # flag=None defaults to 1; tokens=None defaults to []; explicit flag=0 is kept
    assert result["lines"][1]["tokens"] == []
    assert result["lines"][1]["flag"] == 0


# ---------------------------------------------------------------------------
# get_passage_book_code / get_lesson_passage_ids_like
# ---------------------------------------------------------------------------

def test_get_passage_book_code_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_book_code.return_value = "AML"

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "PassageRepository", return_value=repo):
        assert service.get_passage_book_code("AML_1_1") == "AML"


def test_get_lesson_passage_ids_like_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_ids_like.return_value = ["H1_2_1", "H1_2_2"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "PassageRepository", return_value=repo):
        result = service.get_lesson_passage_ids_like("H1_2_%")

    assert result == ["H1_2_1", "H1_2_2"]
    repo.get_ids_like.assert_called_once_with("H1_2_%")
