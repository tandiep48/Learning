import os
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.record import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


# ---------------------------------------------------------------------------
# get_learned_words
# ---------------------------------------------------------------------------

def test_get_learned_words_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_learned_words.return_value = ["你好", "谢谢"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        result = service.get_learned_words(1)

    assert result == ["你好", "谢谢"]
    repo.get_learned_words.assert_called_once_with(1)
    session_local.remove.assert_called_once()


def test_get_learned_words_returns_empty_list_on_db_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_learned_words.side_effect = Exception("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        result = service.get_learned_words(1)

    assert result == []
    session_local.remove.assert_called_once()


# ---------------------------------------------------------------------------
# get_learned_words_last_3_days / get_time_learned_last_3_days
# ---------------------------------------------------------------------------

def test_get_learned_words_last_3_days_formats_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_learned_words_last_3_days.return_value = [
        (date(2026, 7, 24), 120),
        (date(2026, 7, 25), 132),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        result = service.get_learned_words_last_3_days(1)

    assert result == [
        {"date": "2026-07-24", "count": 120},
        {"date": "2026-07-25", "count": 132},
    ]


def test_get_time_learned_last_3_days_computes_minutes():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_time_learned_last_3_days.return_value = [(date(2026, 7, 24), 3_900_000)]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        result = service.get_time_learned_last_3_days(1)

    assert result == [{"date": "2026-07-24", "ms": 3_900_000, "minutes": 65}]


def test_get_time_learned_last_3_days_returns_empty_list_on_db_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_time_learned_last_3_days.side_effect = Exception("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        assert service.get_time_learned_last_3_days(1) == []


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------

def test_get_vocab_record_totals_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_vocab_record_totals.return_value = (10, 50_000)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        assert service.get_vocab_record_totals(1) == (10, 50_000)


def test_get_lesson_record_totals_returns_zeros_on_db_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_lesson_record_totals.side_effect = Exception("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        assert service.get_lesson_record_totals(1) == (0, 0)


def test_get_practice_record_totals_by_category_delegates_to_repository():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_practice_record_totals_by_category.return_value = [("exam", 5, 1000)]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        assert service.get_practice_record_totals_by_category(1) == [("exam", 5, 1000)]


# ---------------------------------------------------------------------------
# get_lesson_progress_by_mode
# ---------------------------------------------------------------------------

def test_get_lesson_progress_by_mode_short_circuits_on_empty_passage_ids():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        assert service.get_lesson_progress_by_mode(1, []) == []

    session_local.assert_not_called()
    repo.get_lesson_progress_by_mode.assert_not_called()


def test_get_lesson_progress_by_mode_formats_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_lesson_progress_by_mode.return_value = [(1, 10, 8, 20_000)]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        result = service.get_lesson_progress_by_mode(1, ["H1_1_1"])

    assert result == [{"mode": 1, "attempts": 10, "correct": 8, "time_ms": 20_000}]
    repo.get_lesson_progress_by_mode.assert_called_once_with(1, ["H1_1_1"])


# ---------------------------------------------------------------------------
# insert_learning_progress / insert_learning_progress_batch
# ---------------------------------------------------------------------------

def test_insert_learning_progress_parses_game_info_json_string_and_commits():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        service.insert_learning_progress(
            user_id=1, session_id=2, mode="typing", word="你好", round_num=1,
            game_info='{"attempt": 1}', user_answer="hello", is_correct=True,
            response_time_ms=500, updated_at="2026-08-23",
        )

    repo.insert_vocab_record.assert_called_once()
    kwargs = repo.insert_vocab_record.call_args.kwargs
    assert kwargs["game_info"] == {"attempt": 1}
    session.commit.assert_called_once()
    session_local.remove.assert_called_once()


def test_insert_learning_progress_rolls_back_on_db_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.insert_vocab_record.side_effect = Exception("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        service.insert_learning_progress(
            user_id=1, session_id=2, mode="typing", word="你好", round_num=1,
            game_info="{}", user_answer="hello", is_correct=True,
            response_time_ms=500, updated_at="2026-08-23",
        )

    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_insert_learning_progress_batch_skips_db_when_records_empty():
    session, session_local = _mock_session()

    with patch.object(service, "SessionLocal", session_local):
        service.insert_learning_progress_batch(user_id=1, session_id=2, records=[], updated_at="2026-08-23")

    session_local.assert_not_called()


def test_insert_learning_progress_batch_normalizes_game_info_and_commits():
    session, session_local = _mock_session()
    repo = MagicMock()
    records = [{"mode": "typing", "word": "你好", "game_info": '{"attempt": 1}'}]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        service.insert_learning_progress_batch(user_id=1, session_id=2, records=records, updated_at="2026-08-23")

    normalized = repo.insert_vocab_records_batch.call_args.kwargs["records"]
    assert normalized[0]["game_info"] == {"attempt": 1}
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# insert_lesson_progress / insert_practice_progress
# ---------------------------------------------------------------------------

def test_insert_lesson_progress_commits():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        service.insert_lesson_progress(
            user_id=1, session_id=2, passage_id="H1_1_1", line_id=1, mode=1,
            game_info="{}", user_answer="a", is_correct=True,
            response_time_ms=100, updated_at="2026-08-23",
        )

    repo.insert_lesson_record.assert_called_once()
    session.commit.assert_called_once()


def test_insert_practice_progress_defaults_category_and_commits():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        service.insert_practice_progress(
            user_id=1, session_id=2, hsk_level=1, lesson="1", question_no=1,
            skill="reading", question_type=1, user_answer="a", is_correct=True,
        )

    kwargs = repo.insert_practice_record.call_args.kwargs
    assert kwargs["category"] == "practice"
    session.commit.assert_called_once()


def test_insert_practice_progress_rolls_back_on_db_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.insert_practice_record.side_effect = Exception("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "RecordRepository", return_value=repo):
        service.insert_practice_progress(
            user_id=1, session_id=2, hsk_level=1, lesson="1", question_no=1,
            skill="reading", question_type=1, user_answer="a", is_correct=True,
        )

    session.rollback.assert_called_once()
