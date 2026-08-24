import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.chinese_stroke_info import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeChineseStrokeInfo:
    def __init__(self, cn="你好", strokes_difficult_cn=3.5):
        self.cn = cn
        self.zh = cn
        self.total_strokes_cn = 9
        self.total_strokes_zh = 9
        self.strokes_cn = "3,6"
        self.strokes_zh = "3,6"
        self.word_length = 2
        self.strokes_difficult_cn = strokes_difficult_cn
        self.strokes_difficult_cn_norm = 0.5
        self.strokes_difficult_zh = strokes_difficult_cn
        self.strokes_difficult_zh_norm = 0.5

    def to_dict(self):
        return {
            "cn": self.cn,
            "zh": self.zh,
            "total_strokes_cn": self.total_strokes_cn,
            "total_strokes_zh": self.total_strokes_zh,
            "strokes_cn": self.strokes_cn,
            "strokes_zh": self.strokes_zh,
            "word_length": self.word_length,
            "strokes_difficult_cn": self.strokes_difficult_cn,
            "strokes_difficult_cn_norm": self.strokes_difficult_cn_norm,
            "strokes_difficult_zh": self.strokes_difficult_zh,
            "strokes_difficult_zh_norm": self.strokes_difficult_zh_norm,
        }


# ---------------------------------------------------------------------------
# get_stroke_info
# ---------------------------------------------------------------------------

def test_get_stroke_info_returns_dict_when_found():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_cn.return_value = FakeChineseStrokeInfo("你好")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ChineseStrokeInfoRepository", return_value=repo):
        result = service.get_stroke_info("你好")

    assert result["cn"] == "你好"
    repo.get_by_cn.assert_called_once_with("你好")
    session_local.remove.assert_called_once()


def test_get_stroke_info_raises_404_when_missing():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_cn.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ChineseStrokeInfoRepository", return_value=repo):
        with pytest.raises(service.ChineseStrokeInfoServiceError) as exc_info:
            service.get_stroke_info("missing")

    assert exc_info.value.status_code == 404


def test_get_stroke_info_rejects_blank_cn():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        with pytest.raises(service.ChineseStrokeInfoServiceError) as exc_info:
            service.get_stroke_info("   ")

    assert exc_info.value.status_code == 400
    session_local.assert_not_called()


# ---------------------------------------------------------------------------
# get_stroke_info_batch
# ---------------------------------------------------------------------------

def test_get_stroke_info_batch_returns_dicts():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_words.return_value = [
        FakeChineseStrokeInfo("你好"),
        FakeChineseStrokeInfo("谢谢"),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ChineseStrokeInfoRepository", return_value=repo):
        result = service.get_stroke_info_batch(["你好", "谢谢"])

    assert [r["cn"] for r in result] == ["你好", "谢谢"]
    repo.get_by_words.assert_called_once_with(["你好", "谢谢"])
    session_local.remove.assert_called_once()


def test_get_stroke_info_batch_dedupes_and_strips_words():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_by_words.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ChineseStrokeInfoRepository", return_value=repo):
        service.get_stroke_info_batch([" 你好 ", "你好", "", None])

    repo.get_by_words.assert_called_once_with(["你好"])


def test_get_stroke_info_batch_returns_empty_list_when_no_words():
    session, session_local = _mock_session()

    with patch.object(service, "SessionLocal", session_local):
        assert service.get_stroke_info_batch([]) == []
        assert service.get_stroke_info_batch(None) == []

    session_local.assert_not_called()
