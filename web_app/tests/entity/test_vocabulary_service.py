import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.vocabulary import service
from entity.vocabulary.service import VocabServiceError


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeVocab:
    def __init__(self, id=1, cn="你好", pinyin="nǐ hǎo", hsk_level="HSK1"):
        self.id = id
        self.cn = cn
        self.pinyin = pinyin
        self.meaning_en = "Hello"
        self.meaning_vn = "Xin chào"
        self.audio_key = None
        self.hsk_level = hsk_level
        self.source = None

    def to_dict(self):
        return {
            "id": self.id, "cn": self.cn, "pinyin": self.pinyin,
            "meaning_en": self.meaning_en, "meaning_vn": self.meaning_vn,
            "audio_key": self.audio_key, "hsk_level": self.hsk_level,
            "source": self.source,
        }


def _fake_integrity_error():
    return IntegrityError("stmt", {}, Exception("duplicate key"))


# ---------------------------------------------------------------------------
# list_vocab
# ---------------------------------------------------------------------------

def test_list_vocab_paginates_and_serializes():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_all.return_value = ([FakeVocab(), FakeVocab(id=2, cn="谢谢")], 2)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        result = service.list_vocab(page=1, page_size=20)

    assert result["total"] == 2
    assert result["total_pages"] == 1
    assert [item["cn"] for item in result["items"]] == ["你好", "谢谢"]
    session_local.remove.assert_called_once()


def test_list_vocab_clamps_page_and_page_size():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_all.return_value = ([], 0)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        service.list_vocab(page=0, page_size=500)

    kwargs = repo.get_all.call_args.kwargs
    assert kwargs["page"] == 1
    assert kwargs["page_size"] == 100


# ---------------------------------------------------------------------------
# get_vocab
# ---------------------------------------------------------------------------

def test_get_vocab_returns_dict_when_found():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_id.return_value = FakeVocab()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        result = service.get_vocab(1)

    assert result["cn"] == "你好"


def test_get_vocab_not_found_raises_404():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_id.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        with pytest.raises(VocabServiceError) as exc:
            service.get_vocab(999)

    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# create_vocab
# ---------------------------------------------------------------------------

def test_create_vocab_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_cn.return_value = None
    repo.create.return_value = FakeVocab()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        result = service.create_vocab({"cn": "你好"})

    assert result["cn"] == "你好"
    session.commit.assert_called_once()
    session_local.remove.assert_called_once()


def test_create_vocab_missing_cn_raises_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(VocabServiceError) as exc:
            service.create_vocab({"cn": "   "})

    assert exc.value.status_code == 400
    session_local.assert_not_called()


def test_create_vocab_rejects_non_string_cn_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(VocabServiceError):
            service.create_vocab({"cn": {"not": "a string"}})

    session_local.assert_not_called()


def test_create_vocab_rejects_invalid_hsk_level_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(VocabServiceError):
            service.create_vocab({"cn": "你好", "hsk_level": "HSK9"})

    session_local.assert_not_called()


def test_create_vocab_duplicate_cn_raises_and_rolls_back():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_cn.return_value = FakeVocab()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        with pytest.raises(VocabServiceError):
            service.create_vocab({"cn": "你好"})

    session.rollback.assert_called_once()
    repo.create.assert_not_called()


def test_create_vocab_integrity_error_raises_service_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_cn.return_value = None
    repo.create.side_effect = _fake_integrity_error()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        with pytest.raises(VocabServiceError):
            service.create_vocab({"cn": "你好"})

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# update_vocab
# ---------------------------------------------------------------------------

def test_update_vocab_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update.return_value = FakeVocab(pinyin="ni3 hao3")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        result = service.update_vocab(1, {"pinyin": "ni3 hao3"})

    assert result["pinyin"] == "ni3 hao3"
    session.commit.assert_called_once()


def test_update_vocab_not_found_raises_404():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        with pytest.raises(VocabServiceError) as exc:
            service.update_vocab(999, {"pinyin": "x"})

    assert exc.value.status_code == 404
    session.rollback.assert_called_once()


def test_update_vocab_empty_payload_raises_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(VocabServiceError):
            service.update_vocab(1, {})

    session_local.assert_not_called()


def test_update_vocab_empty_cn_raises_before_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(VocabServiceError):
            service.update_vocab(1, {"cn": "  "})

    session_local.assert_not_called()


def test_update_vocab_integrity_error_raises_service_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update.side_effect = _fake_integrity_error()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        with pytest.raises(VocabServiceError):
            service.update_vocab(1, {"cn": "谢谢"})

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# delete_vocab
# ---------------------------------------------------------------------------

def test_delete_vocab_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.delete.return_value = True

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        result = service.delete_vocab(1)

    assert "deleted" in result["message"]
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_course_vocab / get_vocab_lessons / get_all_vn_meanings / get_vocabulary_by_words
# ---------------------------------------------------------------------------

def test_get_course_vocab_returns_dataframe_with_expected_columns():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_all_ordered.return_value = [FakeVocab(), FakeVocab(id=2, cn="谢谢")]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        df = service.get_course_vocab()

    assert list(df.columns) == ["word", "pinyin", "meaning_vn", "meaning_en", "audio_key", "level"]
    assert list(df["word"]) == ["你好", "谢谢"]
    session_local.remove.assert_called_once()


def test_get_vocab_lessons_chunks_words():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_words_by_hsk_level.return_value = [f"w{i}" for i in range(12)]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        lessons = service.get_vocab_lessons("HSK1", lesson_size=10)

    assert len(lessons) == 2
    assert lessons[0] == {
        "lesson": 1, "start_idx": 0, "end_idx": 9, "word_count": 10,
        "preview": ["w0", "w1", "w2", "w3"],
    }
    assert lessons[1]["word_count"] == 2


def test_get_vocab_lessons_returns_empty_list_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_words_by_hsk_level.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        assert service.get_vocab_lessons("HSK1") == []


def test_get_all_vn_meanings_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_distinct_vn_meanings.return_value = ["Xin chào", "Cảm ơn"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        assert service.get_all_vn_meanings() == ["Xin chào", "Cảm ơn"]


def test_get_vocabulary_by_words_shapes_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_words.return_value = [FakeVocab()]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        result = service.get_vocabulary_by_words(["你好"])

    assert result == [{
        "word": "你好", "pinyin": "nǐ hǎo", "meaning_vn": "Xin chào",
        "meaning_en": "Hello", "audio_key": None, "hsk_level": "HSK1",
    }]
    repo.get_by_words.assert_called_once_with(["你好"])


def test_get_vocabulary_by_words_returns_empty_list_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        assert service.get_vocabulary_by_words([]) == []
        assert service.get_vocabulary_by_words(None) == []

    session_local.assert_not_called()


def test_delete_vocab_not_found_raises_404():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.delete.return_value = False

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "VocabRepository", return_value=repo):
        with pytest.raises(VocabServiceError) as exc:
            service.delete_vocab(999)

    assert exc.value.status_code == 404
    session.rollback.assert_called_once()
