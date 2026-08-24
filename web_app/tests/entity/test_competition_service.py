import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.competition import service


def _mock_session():
    """Patch service.SessionLocal so no real DB connection is ever opened."""
    session = MagicMock()
    session_local = MagicMock(return_value=session)
    session_local.remove = MagicMock()
    return session, session_local


ROOM_ROW = (1, "ABC123", 42, 1, ["H1_1_1"], 10, 8, 15, "waiting",
            datetime(2026, 8, 1), datetime(2026, 8, 1))


# ---------------------------------------------------------------------------
# resolve_room_words
# ---------------------------------------------------------------------------

def test_resolve_room_words_empty_passage_ids_returns_empty_list():
    assert service.resolve_room_words([]) == []


def test_resolve_room_words_dedups_across_passages():
    def fake_get_passage_vocab(pid):
        return {"p1": [{"cn": "你好"}, {"cn": "谢谢"}], "p2": [{"cn": "谢谢"}, {"cn": "再见"}]}[pid]

    with patch("entity.passage_vocabulary.service.get_passage_vocab", side_effect=fake_get_passage_vocab):
        result = service.resolve_room_words(["p1", "p2"])

    assert [r["cn"] for r in result] == ["你好", "谢谢", "再见"]


# ---------------------------------------------------------------------------
# create_competition_room
# ---------------------------------------------------------------------------

def test_create_competition_room_success_commits_and_returns_room():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.insert_room.return_value = 1

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}) as get_room:
        result = service.create_competition_room("ABC123", 42, 1, ["H1_1_1"], 10, 8, 15)

    repo.upsert_room_member.assert_called_once_with(1, 42, role="host", status="online")
    session.commit.assert_called_once()
    get_room.assert_called_once_with("ABC123")
    assert result == {"id": 1}


def test_create_competition_room_error_rolls_back_and_returns_none():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.insert_room.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.create_competition_room("ABC123", 42, 1, ["H1_1_1"], 10, 8, 15) is None

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_competition_room_by_code
# ---------------------------------------------------------------------------

def test_get_competition_room_by_code_missing_code_returns_none_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        assert service.get_competition_room_by_code(None) is None

    session_local.assert_not_called()


def test_get_competition_room_by_code_shapes_row():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_room_row.return_value = ROOM_ROW

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        result = service.get_competition_room_by_code("abc123")

    assert result["room_code"] == "ABC123"
    assert result["passage_ids"] == ["H1_1_1"]
    assert result["created_at"] == "2026-08-01T00:00:00"


def test_get_competition_room_by_code_not_found_returns_none():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_room_row.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.get_competition_room_by_code("NOPE") is None


def test_get_competition_room_by_code_returns_none_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_room_row.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.get_competition_room_by_code("ABC123") is None


# ---------------------------------------------------------------------------
# join_competition_room
# ---------------------------------------------------------------------------

def test_join_competition_room_room_not_found():
    with patch.object(service, "get_competition_room_by_code", return_value=None):
        result, error = service.join_competition_room("NOPE", 1)

    assert result is None
    assert error == "Room not found"


def test_join_competition_room_full_returns_error_without_commit():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_active_member_count.return_value = 8
    repo.is_room_member.return_value = False
    room = {"id": 1, "max_users": 8, "host_user_id": 42}

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value=room):
        result, error = service.join_competition_room("ABC123", 99)

    assert result is None
    assert error == "Room is full"
    session.commit.assert_not_called()
    repo.upsert_join_member.assert_not_called()


def test_join_competition_room_success_delegates_to_room_state():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_active_member_count.return_value = 1
    repo.is_room_member.return_value = False
    room = {"id": 1, "max_users": 8, "host_user_id": 42}

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value=room), \
         patch.object(service, "get_competition_room_state", return_value={"id": 1}) as get_state:
        result, error = service.join_competition_room("ABC123", 99)

    repo.upsert_join_member.assert_called_once_with(1, 99, "participant")
    session.commit.assert_called_once()
    get_state.assert_called_once_with("ABC123")
    assert result == {"id": 1}
    assert error is None


def test_join_competition_room_error_rolls_back():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_active_member_count.side_effect = RuntimeError("boom")
    room = {"id": 1, "max_users": 8, "host_user_id": 42}

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value=room):
        result, error = service.join_competition_room("ABC123", 99)

    assert result is None
    assert error == "Could not join room"
    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# leave_competition_room
# ---------------------------------------------------------------------------

def test_leave_competition_room_not_found_returns_false():
    with patch.object(service, "get_competition_room_by_code", return_value=None):
        assert service.leave_competition_room("NOPE", 1) is False


def test_leave_competition_room_success_commits_true():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        assert service.leave_competition_room("ABC123", 99) is True

    repo.mark_member_left.assert_called_once_with(1, 99)
    session.commit.assert_called_once()


def test_leave_competition_room_error_rolls_back_false():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.mark_member_left.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        assert service.leave_competition_room("ABC123", 99) is False

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_competition_room_state
# ---------------------------------------------------------------------------

def test_get_competition_room_state_not_found_returns_none():
    with patch.object(service, "get_competition_room_by_code", return_value=None):
        assert service.get_competition_room_state("NOPE") is None


def test_get_competition_room_state_shapes_members_chat_and_session():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_room_members.return_value = [
        (42, "host_user", "host", "online", datetime(2026, 8, 1)),
    ]
    repo.get_recent_chat.return_value = [
        (2, 42, "host_user", "second", datetime(2026, 8, 1, 0, 1)),
        (1, 42, "host_user", "first", datetime(2026, 8, 1, 0, 0)),
    ]
    repo.get_latest_session_row.return_value = (
        9, "running", "vocab", datetime(2026, 8, 1), datetime(2026, 8, 1),
        datetime(2026, 8, 1), None,
    )

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        room = service.get_competition_room_state("ABC123")

    assert room["members"][0]["username"] == "host_user"
    # reversed() so chat comes back oldest-first even though the query is newest-first.
    assert [c["message"] for c in room["chat"]] == ["first", "second"]
    assert room["session"]["id"] == 9


def test_get_competition_room_state_returns_none_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_room_members.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        assert service.get_competition_room_state("ABC123") is None


# ---------------------------------------------------------------------------
# add_competition_chat_message
# ---------------------------------------------------------------------------

def test_add_competition_chat_message_empty_text_returns_none_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        assert service.add_competition_chat_message("ABC123", 42, "   ") is None

    session_local.assert_not_called()


def test_add_competition_chat_message_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.insert_chat_message.return_value = (5, datetime(2026, 8, 1))
    repo.get_username.return_value = "host_user"

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        result = service.add_competition_chat_message("ABC123", 42, "hi")

    assert result == {
        "id": 5, "user_id": 42, "username": "host_user",
        "message": "hi", "created_at": "2026-08-01T00:00:00",
    }
    session.commit.assert_called_once()


def test_add_competition_chat_message_error_rolls_back():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.insert_chat_message.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        assert service.add_competition_chat_message("ABC123", 42, "hi") is None

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# start_competition_session
# ---------------------------------------------------------------------------

def test_start_competition_session_room_not_found():
    with patch.object(service, "get_competition_room_by_code", return_value=None):
        result, error = service.start_competition_session("NOPE", 42)
    assert (result, error) == (None, "Room not found")


def test_start_competition_session_not_host():
    room = {"id": 1, "host_user_id": 42, "status": "waiting", "passage_ids": ["H1_1_1"]}
    with patch.object(service, "get_competition_room_by_code", return_value=room):
        result, error = service.start_competition_session("ABC123", 99)
    assert (result, error) == (None, "Only the host can start")


def test_start_competition_session_already_running():
    room = {"id": 1, "host_user_id": 42, "status": "running", "passage_ids": ["H1_1_1"]}
    with patch.object(service, "get_competition_room_by_code", return_value=room):
        result, error = service.start_competition_session("ABC123", 42)
    assert (result, error) == (None, "Room is already running")


def test_start_competition_session_no_vocab():
    room = {"id": 1, "host_user_id": 42, "status": "waiting", "passage_ids": []}
    with patch.object(service, "get_competition_room_by_code", return_value=room):
        result, error = service.start_competition_session("ABC123", 42)
    assert (result, error) == (None, "No vocabulary selected")


def test_start_competition_session_success():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.insert_session.return_value = 7
    room = {
        "id": 1, "host_user_id": 42, "status": "waiting",
        "passage_ids": ["H1_1_1"], "section_timeout_minutes": 15,
    }

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value=room), \
         patch.object(service, "get_competition_session_state", return_value={"id": 7}) as get_state:
        result, error = service.start_competition_session("ABC123", 42)

    repo.update_room_status.assert_called_once_with(1, "running")
    repo.insert_session.assert_called_once_with(1, 15)
    repo.seed_scores_for_session.assert_called_once_with(7, 1)
    session.commit.assert_called_once()
    get_state.assert_called_once_with(7)
    assert result == {"id": 7}
    assert error is None


def test_start_competition_session_error_rolls_back():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update_room_status.side_effect = RuntimeError("boom")
    room = {
        "id": 1, "host_user_id": 42, "status": "waiting",
        "passage_ids": ["H1_1_1"], "section_timeout_minutes": 15,
    }

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value=room):
        result, error = service.start_competition_session("ABC123", 42)

    assert (result, error) == (None, "Could not start session")
    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_active_competition_session
# ---------------------------------------------------------------------------

def test_get_active_competition_session_room_not_found():
    with patch.object(service, "get_competition_room_by_code", return_value=None):
        assert service.get_active_competition_session("NOPE") is None


def test_get_active_competition_session_no_session_row():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_latest_session_id.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}):
        assert service.get_active_competition_session("ABC123") is None


def test_get_active_competition_session_delegates_to_session_state():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_latest_session_id.return_value = (7,)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_room_by_code", return_value={"id": 1}), \
         patch.object(service, "get_competition_session_state", return_value={"id": 7}) as get_state:
        result = service.get_active_competition_session("ABC123")

    get_state.assert_called_once_with(7)
    assert result == {"id": 7}


# ---------------------------------------------------------------------------
# get_competition_session_state
# ---------------------------------------------------------------------------

def test_get_competition_session_state_missing_id_returns_none_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        assert service.get_competition_session_state(None) is None

    session_local.assert_not_called()


def test_get_competition_session_state_not_found_returns_none():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_session_row.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.get_competition_session_state(7) is None


def test_get_competition_session_state_shapes_row_and_attaches_scores():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_session_row.return_value = (
        7, 1, "ABC123", "running", "vocab",
        datetime(2026, 8, 1), datetime(2026, 8, 1), datetime(2026, 8, 1), None,
    )

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_scores", return_value=[{"user_id": 42}]) as get_scores:
        state = service.get_competition_session_state(7)

    assert state["room_code"] == "ABC123"
    assert state["scores"] == [{"user_id": 42}]
    get_scores.assert_called_once_with(7)


# ---------------------------------------------------------------------------
# calculate_competition_points
# ---------------------------------------------------------------------------

def test_calculate_competition_points_unknown_activity_returns_zero():
    assert service.calculate_competition_points("unknown", True, 1000) == 0


def test_calculate_competition_points_incorrect_returns_zero():
    assert service.calculate_competition_points("typing", False, 1000) == 0


def test_calculate_competition_points_correct_computes_base_plus_bonus_minus_penalty():
    # listen: base=100, max_bonus=50, decay=2.0, penalty_rate=0.10
    # 500ms -> 0.5s -> bonus = 50 - 0.5*2 = 49; 1 wrong attempt -> penalty = 100*0.10 = 10
    points = service.calculate_competition_points("listen", True, 500, wrong_attempts=1)
    assert points == round((100 - 10) + 49)


# ---------------------------------------------------------------------------
# record_competition_vocab_answer
# ---------------------------------------------------------------------------

def test_record_competition_vocab_answer_invalid_payload_returns_error_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        result, error = service.record_competition_vocab_answer(7, 42, "", "typing", True, 500)

    assert (result, error) == (None, "Invalid answer payload")
    session_local.assert_not_called()


def test_record_competition_vocab_answer_inactive_session_returns_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.is_session_active_for_user.return_value = False

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        result, error = service.record_competition_vocab_answer(7, 42, "你好", "typing", True, 500)

    assert (result, error) == (None, "Session is not active")


def test_record_competition_vocab_answer_duplicate_returns_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.is_session_active_for_user.return_value = True
    repo.insert_vocab_answer.return_value = None

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        result, error = service.record_competition_vocab_answer(7, 42, "你好", "typing", True, 500)

    assert (result, error) == (None, "Answer already submitted")
    repo.increment_score.assert_not_called()


def test_record_competition_vocab_answer_success_commits_and_returns_scores():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.is_session_active_for_user.return_value = True
    repo.insert_vocab_answer.return_value = (1,)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_scores", return_value=[{"user_id": 42}]):
        result, error = service.record_competition_vocab_answer(7, 42, "你好", "typing", True, 500)

    assert error is None
    assert result["is_correct"] is True
    assert result["scores"] == [{"user_id": 42}]
    repo.increment_score.assert_called_once()
    session.commit.assert_called_once()


def test_record_competition_vocab_answer_error_rolls_back():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.is_session_active_for_user.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        result, error = service.record_competition_vocab_answer(7, 42, "你好", "typing", True, 500)

    assert (result, error) == (None, "Could not record answer")
    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_competition_scores
# ---------------------------------------------------------------------------

def test_get_competition_scores_missing_id_returns_empty_list_without_touching_db():
    session, session_local = _mock_session()
    with patch.object(service, "SessionLocal", session_local):
        assert service.get_competition_scores(None) == []

    session_local.assert_not_called()


def test_get_competition_scores_shapes_rows():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_scores_rows.return_value = [
        (42, "host_user", 10, 5, 15, 1200, 1, datetime(2026, 8, 1)),
    ]

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        scores = service.get_competition_scores(7)

    assert scores == [{
        "user_id": 42, "username": "host_user", "listening_points": 10,
        "reading_points": 5, "total_points": 15, "total_response_time_ms": 1200,
        "rank": 1, "finished_at": "2026-08-01T00:00:00",
    }]


def test_get_competition_scores_returns_empty_list_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_scores_rows.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.get_competition_scores(7) == []


# ---------------------------------------------------------------------------
# mark_competition_participant_finished
# ---------------------------------------------------------------------------

def test_mark_competition_participant_finished_success():
    session, session_local = _mock_session()
    repo = MagicMock()

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.mark_competition_participant_finished(7, 42) is True

    repo.mark_score_finished.assert_called_once_with(7, 42)
    session.commit.assert_called_once()


def test_mark_competition_participant_finished_error_rolls_back():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.mark_score_finished.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.mark_competition_participant_finished(7, 42) is False

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# competition_all_participants_finished
# ---------------------------------------------------------------------------

def test_competition_all_participants_finished_true_when_all_done():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_finished_counts.return_value = (3, 3)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.competition_all_participants_finished(7) is True


def test_competition_all_participants_finished_false_when_none_scored():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_finished_counts.return_value = (0, 0)

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.competition_all_participants_finished(7) is False


def test_competition_all_participants_finished_returns_false_on_error():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.get_finished_counts.side_effect = RuntimeError("boom")

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo):
        assert service.competition_all_participants_finished(7) is False


# ---------------------------------------------------------------------------
# finalize_competition_session
# ---------------------------------------------------------------------------

def test_finalize_competition_session_missing_state_returns_none():
    with patch.object(service, "get_competition_session_state", return_value=None):
        assert service.finalize_competition_session(7) is None


def test_finalize_competition_session_already_ranked_is_idempotent():
    session, session_local = _mock_session()
    ranked_state = {"status": "ranked", "id": 7}

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "get_competition_session_state", return_value=ranked_state):
        result = service.finalize_competition_session(7)

    assert result == ranked_state
    session_local.assert_not_called()


def test_finalize_competition_session_ranks_and_reopens_room():
    session, session_local = _mock_session()
    repo = MagicMock()
    running_state = {"status": "running", "id": 7}
    final_state = {"status": "ranked", "id": 7}

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_session_state", side_effect=[running_state, final_state]):
        result = service.finalize_competition_session(7)

    repo.update_session_status.assert_called_once_with(7, "ranked", finished=True)
    repo.rank_scores.assert_called_once_with(7)
    repo.reopen_room_for_session.assert_called_once_with(7)
    session.commit.assert_called_once()
    assert result == final_state


def test_finalize_competition_session_error_rolls_back_and_returns_none():
    session, session_local = _mock_session()
    repo = MagicMock()
    repo.update_session_status.side_effect = RuntimeError("boom")
    running_state = {"status": "running", "id": 7}

    with patch.object(service, "SessionLocal", session_local), \
         patch.object(service, "CompetitionRepository", return_value=repo), \
         patch.object(service, "get_competition_session_state", return_value=running_state):
        assert service.finalize_competition_session(7) is None

    session.rollback.assert_called_once()
