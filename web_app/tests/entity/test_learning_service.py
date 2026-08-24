import os
import sys
from datetime import date, datetime
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.learning import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


# ---------------------------------------------------------------------------
# get_mastered_words_with_recency
# ---------------------------------------------------------------------------

def test_get_mastered_words_with_recency_shapes_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    when = datetime(2026, 8, 1)
    repo.get_mastered_words_with_recency.return_value = [("你好", when)]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        result = service.get_mastered_words_with_recency(1)

    assert result == [{"word": "你好", "learned_at": when}]
    session_local.remove.assert_called_once()


def test_get_mastered_words_with_recency_returns_empty_list_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_mastered_words_with_recency.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_mastered_words_with_recency(1) == []

    session_local.remove.assert_called_once()


# ---------------------------------------------------------------------------
# get_mastered_words_page
# ---------------------------------------------------------------------------

def test_get_mastered_words_page_shapes_and_paginates():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_mastered_words_total.return_value = 30
    repo.get_mastered_words_rows.return_value = [
        ("你好", date(2026, 8, 1), "nǐ hǎo", "Xin chào", "Hello", "audio.mp3", "HSK1"),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        result = service.get_mastered_words_page(1, page=2, page_size=10)

    assert result["total"] == 30
    assert result["total_pages"] == 3
    assert result["page"] == 2
    repo.get_mastered_words_rows.assert_called_once_with(1, 10, 10)
    assert result["rows"] == [{
        "word": "你好", "cn": "你好", "learned_at": "2026-08-01",
        "pinyin": "nǐ hǎo", "meaning_vn": "Xin chào", "meaning_en": "Hello",
        "audio_key": "audio.mp3", "hsk_level": "HSK1", "level": "HSK1",
    }]


def test_get_mastered_words_page_clamps_page_past_last_page():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_mastered_words_total.return_value = 5
    repo.get_mastered_words_rows.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        result = service.get_mastered_words_page(1, page=99, page_size=10)

    assert result["page"] == 1
    assert result["total_pages"] == 1


def test_get_mastered_words_page_returns_safe_default_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_mastered_words_total.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        result = service.get_mastered_words_page(1)

    assert result == {"rows": [], "page": 1, "page_size": 24, "total": 0, "total_pages": 1}


# ---------------------------------------------------------------------------
# get_recommended_practices
# ---------------------------------------------------------------------------

def test_get_recommended_practices_returns_empty_when_nothing_mastered():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", return_value=[]):
        assert service.get_recommended_practices(1) == []

    session_local.remove.assert_called_once()


def test_get_recommended_practices_filters_by_threshold_and_attaches_metadata():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_group_words_coverage.return_value = [
        ("practice", 1, 1, "p1", 10, 9, ["w1", "w2"]),  # coverage 0.9 -> ready
        ("practice", 1, 2, "p2", 10, 5, ["w3"]),         # coverage 0.5 -> not ready
    ]
    repo.get_group_latest_status.return_value = [
        ("practice", 1, 1, "p1", 1.0),
    ]
    repo.get_group_metadata.return_value = [
        ("practice", 1, 1, "p1", 5, "listening", 1, ["u1", "u2"]),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", return_value=["w1", "w2"]), \
         patch.object(service, "LearningRepository", return_value=repo):
        results = service.get_recommended_practices(1, threshold=0.80)

    assert len(results) == 1
    item = results[0]
    assert item["status"] == "Finish and success"
    assert item["question_count"] == 5
    assert item["skill"] == "listening"
    assert item["unit_ids"] == ["u1", "u2"]
    assert item["coverage_pct"] == 90.0


def test_get_recommended_practices_status_filter_excludes_non_matching_groups():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_group_words_coverage.return_value = [
        ("practice", 1, 1, "p1", 10, 9, ["w1"]),
    ]
    repo.get_group_latest_status.return_value = [
        ("practice", 1, 1, "p1", 1.0),  # -> "Finish and success"
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", return_value=["w1"]), \
         patch.object(service, "LearningRepository", return_value=repo):
        results = service.get_recommended_practices(1, status_filter="Not start")

    assert results == []
    repo.get_group_metadata.assert_not_called()


def test_get_recommended_practices_returns_empty_list_on_error():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", side_effect=RuntimeError("boom")):
        assert service.get_recommended_practices(1) == []


# ---------------------------------------------------------------------------
# get_practice_history_sessions
# ---------------------------------------------------------------------------

def test_get_practice_history_sessions_shapes_rows_and_detects_next_page():
    session, session_local = _mock_session()
    repo = MagicMock()
    ended = datetime(2026, 8, 1, 12, 0, 0)
    repo.list_practice_sessions.return_value = [
        (1, ended, 10, 8, [1], ["1"], ["practice"]),
        (2, ended, 5, 5, [1], ["2"], ["exam"]),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        sessions, has_more = service.get_practice_history_sessions(1, page_size=1)

    assert has_more is True
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == 1
    assert sessions[0]["score_pct"] == 80.0
    assert sessions[0]["ended_at"] == ended.isoformat()


def test_get_practice_history_sessions_returns_safe_default_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.list_practice_sessions.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_practice_history_sessions(1) == ([], False)


# ---------------------------------------------------------------------------
# get_practice_session_detail
# ---------------------------------------------------------------------------

def test_get_practice_session_detail_zips_columns():
    session, session_local = _mock_session()
    repo = MagicMock()
    answered = datetime(2026, 8, 1)
    repo.get_practice_session_rows.return_value = [
        (1, "1", 1, "listening", 1, "A", True, answered, "practice",
         "content", "question?", "A", "audio.mp3", None, {"A": True}, "p1"),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        result = service.get_practice_session_detail(1, 99)

    assert result == [{
        "level": 1, "lesson": "1", "no": 1, "skill": "listening", "type": 1,
        "user_answer": "A", "is_correct": True, "answered_at": answered,
        "category": "practice", "content": "content", "question": "question?",
        "answer": "A", "audio_key": "audio.mp3", "image": None,
        "options": {"A": True}, "progress": "p1",
    }]


def test_get_practice_session_detail_returns_none_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_practice_session_rows.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_practice_session_detail(1, 99) is None


# ---------------------------------------------------------------------------
# get_unlearned_words_from_db / get_unsure_words_from_db
# ---------------------------------------------------------------------------

def test_get_unlearned_words_from_db_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_unlearned_words.return_value = ["谢谢"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_unlearned_words_from_db(1) == ["谢谢"]


def test_get_unlearned_words_from_db_returns_empty_list_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_unlearned_words.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_unlearned_words_from_db(1) == []


def test_get_unsure_words_from_db_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_unsure_words.return_value = ["谢谢"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_unsure_words_from_db(1) == ["谢谢"]


def test_get_unsure_words_from_db_returns_empty_list_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_unsure_words.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_unsure_words_from_db(1) == []


# ---------------------------------------------------------------------------
# get_review_words / get_review_words_flat
# ---------------------------------------------------------------------------

def test_get_review_words_orders_critical_then_unsure_then_incomplete():
    with patch.object(service, "get_unsure_words_from_db", return_value=["a", "b"]), \
         patch.object(service, "get_unlearned_words_from_db", return_value=["b", "c"]):
        result = service.get_review_words(1)

    assert result == [
        {"word": "b", "reason": "critical"},
        {"word": "a", "reason": "unsure"},
        {"word": "c", "reason": "incomplete"},
    ]


def test_get_review_words_flat_returns_word_list_only():
    with patch.object(service, "get_unsure_words_from_db", return_value=["a"]), \
         patch.object(service, "get_unlearned_words_from_db", return_value=["b"]):
        assert service.get_review_words_flat(1) == ["a", "b"]


# ---------------------------------------------------------------------------
# get_hard_semantic_learned_words / get_hard_stroke_learned_words
# ---------------------------------------------------------------------------

def test_get_hard_semantic_learned_words_dedups_while_preserving_order():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_hard_semantic_words_ordered.return_value = ["难", "难", "易"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_hard_semantic_learned_words(1) == ["难", "易"]


def test_get_hard_semantic_learned_words_returns_empty_list_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_hard_semantic_words_ordered.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_hard_semantic_learned_words(1) == []


def test_get_hard_stroke_learned_words_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_hard_stroke_words_ordered.return_value = ["繁", "简"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_hard_stroke_learned_words(1) == ["繁", "简"]


def test_get_hard_stroke_learned_words_returns_empty_list_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_hard_stroke_words_ordered.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "LearningRepository", return_value=repo):
        assert service.get_hard_stroke_learned_words(1) == []
