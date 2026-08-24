import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.progress import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


class FakeBook:
    def __init__(self, book_code="AML", name_en="A Month in Life", name_vn="Một tháng"):
        self.book_code = book_code
        self.name_en = name_en
        self.name_vn = name_vn


# ---------------------------------------------------------------------------
# set_recent_learning / get_recent_learning
# ---------------------------------------------------------------------------

def test_set_recent_learning_missing_passage_id_returns_false_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        assert service.set_recent_learning(1, None) is False

    session_local.assert_not_called()


def test_set_recent_learning_success_commits():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.set_recent_learning(1, "H1_1_1") is True

    repo.upsert_recent_learning.assert_called_once_with(1, "H1_1_1")
    session.commit.assert_called_once()
    session_local.remove.assert_called_once()


def test_set_recent_learning_error_rolls_back_and_returns_false():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.upsert_recent_learning.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.set_recent_learning(1, "H1_1_1") is False

    session.rollback.assert_called_once()


def test_get_recent_learning_returns_dict_when_found():
    session, session_local = _mock_session()
    repo = MagicMock()
    when = datetime(2026, 8, 1)
    repo.get_recent_learning_row.return_value = ("H1_1_1", when)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        result = service.get_recent_learning(1)

    assert result == {"passage_id": "H1_1_1", "updated_at": when.isoformat()}


def test_get_recent_learning_returns_none_when_not_found():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_recent_learning_row.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.get_recent_learning(1) is None


def test_get_recent_learning_returns_none_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_recent_learning_row.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.get_recent_learning(1) is None


# ---------------------------------------------------------------------------
# mark_lesson_part_completed
# ---------------------------------------------------------------------------

def test_mark_lesson_part_completed_missing_passage_id_returns_false_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        assert service.mark_lesson_part_completed(1, None) is False

    session_local.assert_not_called()


def test_mark_lesson_part_completed_success_commits():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.mark_lesson_part_completed(1, "H1_1_1", completed=True, score_pct=90) is True

    repo.upsert_lesson_part_progress.assert_called_once_with(1, "H1_1_1", True, 90)
    session.commit.assert_called_once()


def test_mark_lesson_part_completed_error_rolls_back_and_returns_false():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.upsert_lesson_part_progress.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.mark_lesson_part_completed(1, "H1_1_1") is False

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_lesson_picker_progress
# ---------------------------------------------------------------------------

def test_get_lesson_picker_progress_aggregates_parts_and_lessons():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_passage_vocab_rows.return_value = [
        ("H1_1_1", "你好"),
        ("H1_1_1", "谢谢"),
        ("H1_1_2", "再见"),
    ]
    repo.get_user_lesson_part_progress.return_value = [
        ("H1_1_1", datetime(2026, 8, 1), 100),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", return_value=["你好"]), \
         patch.object(service, "ProgressRepository", return_value=repo):
        result = service.get_lesson_picker_progress(1, "HSK1")

    part = result["parts"]["H1_1_1"]
    assert part["total_words"] == 2
    assert part["learned_words"] == 1
    assert part["lesson_learned"] == 1
    assert part["progress_pct"] == 100

    lesson = result["lessons"]["1"]
    assert lesson["total_words"] == 3
    assert lesson["learned_words"] == 1
    assert lesson["lesson_learned"] == 1
    assert lesson["lesson_total"] == 2


def test_get_lesson_picker_progress_returns_safe_default_on_error():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", side_effect=RuntimeError("boom")):
        assert service.get_lesson_picker_progress(1, "HSK1") == {"lessons": {}, "parts": {}}


# ---------------------------------------------------------------------------
# get_books_summary
# ---------------------------------------------------------------------------

def test_get_books_summary_groups_by_book_and_counts_completion():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_book_passage_rows.return_value = [
        ("AML_1_1", "AML"),
        ("AML_2_1", "AML"),
    ]
    repo.get_book_names.return_value = [("AML", "A Month in Life", "Một tháng")]
    repo.get_completed_passage_ids.return_value = {"AML_1_1"}

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        result = service.get_books_summary(1, lang="en")

    assert result == [{
        "book_code": "AML", "name": "A Month in Life", "cover_url": "/lesson-cover/AML",
        "part_count": 2, "done_count": 1, "lesson_count": 2,
    }]


def test_get_books_summary_localizes_name_for_vietnamese():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_book_passage_rows.return_value = [("AML_1_1", "AML")]
    repo.get_book_names.return_value = [("AML", "A Month in Life", "Một tháng")]
    repo.get_completed_passage_ids.return_value = set()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        result = service.get_books_summary(1, lang="vi")

    assert result[0]["name"] == "Một tháng"


# ---------------------------------------------------------------------------
# get_book_lessons
# ---------------------------------------------------------------------------

def test_get_book_lessons_returns_none_for_unknown_book():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_book_passages_with_titles.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.get_book_lessons(1, "NOPE") is None


def test_get_book_lessons_builds_ordered_lessons_with_parts():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_book_passages_with_titles.return_value = [
        ("AML_2_1", "Lesson Two", "Bài Hai"),
        ("AML_10_1", "Lesson Ten", "Bài Mười"),
    ]
    repo.get_book.return_value = FakeBook()
    repo.get_user_lesson_part_progress.return_value = [
        ("AML_2_1", datetime(2026, 8, 1), 100),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        result = service.get_book_lessons(1, "AML", lang="en")

    assert result["book_name"] == "A Month in Life"
    # Numeric-aware ordering: lesson "2" before lesson "10".
    assert [lesson["lesson"] for lesson in result["lessons"]] == ["2", "10"]
    lesson_2 = result["lessons"][0]
    assert lesson_2["title"] == "Lesson Two"
    assert lesson_2["done_count"] == 1
    assert lesson_2["parts"][0]["completed"] is True
    assert lesson_2["parts"][0]["progress_pct"] == 100


# ---------------------------------------------------------------------------
# mark_passage_words_mastered
# ---------------------------------------------------------------------------

def test_mark_passage_words_mastered_missing_passage_id_returns_zero_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        assert service.mark_passage_words_mastered(1, None) == 0

    session_local.assert_not_called()


def test_mark_passage_words_mastered_no_vocab_returns_zero():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_passage_vocab_words.return_value = []

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.mark_passage_words_mastered(1, "H1_1_1") == 0

    repo.insert_vocab_mastery_records.assert_not_called()


def test_mark_passage_words_mastered_skips_already_mastered_words():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_passage_vocab_words.return_value = ["你好"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", return_value=["你好"]), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.mark_passage_words_mastered(1, "H1_1_1") == 0

    repo.insert_vocab_mastery_records.assert_not_called()


def test_mark_passage_words_mastered_inserts_three_mode_rows_per_pending_word():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_passage_vocab_words.return_value = ["你好", "谢谢"]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_learned_words", return_value=["你好"]), \
         patch.object(service, "ProgressRepository", return_value=repo):
        count = service.mark_passage_words_mastered(1, "H1_1_1")

    assert count == 1
    inserted_rows = repo.insert_vocab_mastery_records.call_args.args[0]
    assert len(inserted_rows) == 3
    assert {r["mode"] for r in inserted_rows} == {"typing", "listen", "meaning"}
    assert all(r["word"] == "谢谢" for r in inserted_rows)
    session.commit.assert_called_once()


def test_mark_passage_words_mastered_error_rolls_back_and_returns_zero():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_passage_vocab_words.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "ProgressRepository", return_value=repo):
        assert service.mark_passage_words_mastered(1, "H1_1_1") == 0

    session.rollback.assert_called_once()
