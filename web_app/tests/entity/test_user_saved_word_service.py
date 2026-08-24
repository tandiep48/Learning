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
