import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.user_saved_word import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeVocab:
    def __init__(self, cn="你好", pinyin="nǐ hǎo", meaning_vn=None, meaning_en=None,
                 audio_key=None, hsk_level=None):
        self.cn = cn
        self.pinyin = pinyin
        self.meaning_vn = meaning_vn
        self.meaning_en = meaning_en
        self.audio_key = audio_key
        self.hsk_level = hsk_level


def test_get_user_saved_vocab_shapes_rows_with_empty_string_fallback():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.list_vocab.return_value = [FakeVocab()]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserSavedWordRepository", return_value=repo):
        result = service.get_user_saved_vocab(1, "H1_1_1")

    assert result == [{
        "cn": "你好", "pinyin": "nǐ hǎo", "meaning_vn": "", "meaning_en": "",
        "audio_key": "", "hsk_level": "",
    }]
    repo.list_vocab.assert_called_once_with(1, "H1_1_1")
    session_local.remove.assert_called_once()


def test_get_user_saved_vocab_by_book_shapes_rows_with_empty_string_fallback():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.list_vocab_by_book.return_value = [
        FakeVocab(cn="谢谢", pinyin="xièxie", meaning_en="thanks", hsk_level="1"),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserSavedWordRepository", return_value=repo):
        result = service.get_user_saved_vocab_by_book(7, "HSK1")

    assert result == [{
        "cn": "谢谢", "pinyin": "xièxie", "meaning_vn": "", "meaning_en": "thanks",
        "audio_key": "", "hsk_level": "1",
    }]
    repo.list_vocab_by_book.assert_called_once_with(7, "HSK1")
    session_local.remove.assert_called_once()


def test_get_user_saved_vocab_by_book_returns_empty_when_no_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.list_vocab_by_book.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserSavedWordRepository", return_value=repo):
        assert service.get_user_saved_vocab_by_book(7, "HSK1") == []

    session_local.remove.assert_called_once()


# ----------------------------------------------------------------------
# get_user_saved_book_passages
# ----------------------------------------------------------------------

def test_get_user_saved_book_passages_returns_repository_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.list_book_passage_ids.return_value = ["GCS_1_1", "GCS_1_2"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserSavedWordRepository", return_value=repo):
        result = service.get_user_saved_book_passages(7, "  GCS  ")

    assert result == ["GCS_1_1", "GCS_1_2"]
    repo.list_book_passage_ids.assert_called_once_with(7, "GCS")
    session_local.remove.assert_called_once()


def test_get_user_saved_book_passages_skips_db_without_book_code():
    session, session_local = _mock_session()

    with patch.object(service, "SessionLocal", session_local):
        assert service.get_user_saved_book_passages(7, "") == []
        assert service.get_user_saved_book_passages(7, None) == []

    session_local.assert_not_called()


# ----------------------------------------------------------------------
# get_competition_book_words
# ----------------------------------------------------------------------

def test_get_competition_book_words_shapes_rows_for_the_vocab_trainer():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.list_vocab_for_users_in_passages.return_value = [
        FakeVocab(cn="书", pinyin="shū", meaning_vn="sách", hsk_level="1"),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "UserSavedWordRepository", return_value=repo):
        result = service.get_competition_book_words(["3", 4], ["GCS_1_1"])

    assert result == [{
        "word": "书", "cn": "书", "pinyin": "shū", "meaning_vn": "sách",
        "meaning_en": "", "audio_key": "", "level": "1",
    }]
    repo.list_vocab_for_users_in_passages.assert_called_once_with([3, 4], ["GCS_1_1"])
    session_local.remove.assert_called_once()


def test_get_competition_book_words_skips_db_when_either_side_is_empty():
    session, session_local = _mock_session()

    with patch.object(service, "SessionLocal", session_local):
        assert service.get_competition_book_words([], ["GCS_1_1"]) == []
        assert service.get_competition_book_words([1], []) == []
        assert service.get_competition_book_words(None, None) == []

    session_local.assert_not_called()
