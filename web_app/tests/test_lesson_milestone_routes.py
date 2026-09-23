"""GET / POST /api/lesson/milestone.

The property that matters is that the two graded steps are *derived*, never
trusted from the milestone table: step 3 from full word mastery, step 6 from
user_lesson_part_progress.lesson_trainer_completed_at. That is what keeps the
milestone in step with the rest of the app, and it is also the whole backfill
story — a learner who finished a part before this shipped must see 6/6 with no
stored rows at all.
"""
import os
import sys
from datetime import datetime, timezone

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from entity.user_lesson_milestone import service as milestone_service
from routes.lesson import lesson_routes


PASSAGE = "H1_2_1"
PART_WORDS = ["你好", "学习", "汉语"]
TRAINER_DONE_AT = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


class StubUser:
    id = 1
    is_authenticated = True


class FakeRepo:
    """Stands in for MilestoneRepository — the service's only database contact."""

    def __init__(self, stored=None, trainer_completed_at=None):
        # {step: completed_at or None}
        self.stored = dict(stored or {})
        self.trainer_completed_at = trainer_completed_at
        self.writes = []

    def get_completed_steps(self, user_id, passage_id):
        return dict(self.stored)

    def get_lesson_trainer_completed_at(self, user_id, passage_id):
        return self.trainer_completed_at

    def mark_step(self, user_id, passage_id, step):
        self.writes.append(step)
        # ON CONFLICT DO NOTHING: the first timestamp wins.
        self.stored.setdefault(step, datetime(2026, 9, 20, tzinfo=timezone.utc))


class FakeSession:
    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(lesson_routes, "current_user", StubUser())
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.register_blueprint(lesson_routes.lesson_bp)
    with app.test_client() as c:
        yield c


def wire(monkeypatch, repo, *, part_vocab=PART_WORDS, learned=()):
    """Point the service at a fake repo and fake mastery data."""
    monkeypatch.setattr(milestone_service, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(milestone_service.SessionLocal, "remove", lambda: None, raising=False)
    monkeypatch.setattr(milestone_service, "MilestoneRepository", lambda session: repo)
    monkeypatch.setattr(
        milestone_service, "get_passage_vocab", lambda pid: [{"cn": w} for w in part_vocab]
    )
    monkeypatch.setattr(milestone_service, "get_learned_words", lambda uid: list(learned))


def get_milestone(client, passage_id=PASSAGE):
    response = client.get(f"/api/lesson/milestone?passage_id={passage_id}")
    assert response.status_code == 200
    return response.get_json()


def completed_steps(payload):
    return [s["step"] for s in payload["steps"] if s["completed"]]


# ---------------------------------------------------------------------------
# GET — derivation
# ---------------------------------------------------------------------------

def test_derives_all_six_from_lesson_trainer_with_no_stored_rows(client, monkeypatch):
    """The backfill story: an old completion reads as 6/6 with an empty table."""
    repo = FakeRepo(stored={}, trainer_completed_at=TRAINER_DONE_AT)
    wire(monkeypatch, repo)

    payload = get_milestone(client)

    assert completed_steps(payload) == [1, 2, 3, 4, 5, 6]
    assert payload["current_step"] == 7
    assert payload["total_steps"] == 6
    assert repo.stored == {}, "deriving must not write rows"


def test_fills_in_every_step_below_the_highest_completed(client, monkeypatch):
    """Storing step 5 alone implies 1-4 were walked to reach it."""
    wire(monkeypatch, FakeRepo(stored={5: TRAINER_DONE_AT}))

    payload = get_milestone(client)

    assert completed_steps(payload) == [1, 2, 3, 4, 5]
    assert payload["current_step"] == 6


def test_step_3_derives_from_full_word_mastery_not_a_stored_row(client, monkeypatch):
    wire(monkeypatch, FakeRepo(stored={}), learned=PART_WORDS)

    payload = get_milestone(client)

    assert 3 in completed_steps(payload)
    # ...and 1-2 fill in below it.
    assert completed_steps(payload) == [1, 2, 3]
    assert payload["current_step"] == 4


def test_step_3_stays_incomplete_when_one_word_is_unmastered(client, monkeypatch):
    wire(monkeypatch, FakeRepo(stored={}), learned=PART_WORDS[:-1])

    payload = get_milestone(client)

    assert completed_steps(payload) == []
    assert payload["current_step"] == 1


def test_a_part_with_no_vocab_does_not_get_step_3_for_free(client, monkeypatch):
    """An empty word set is a subset of anything — guard against vacuous mastery."""
    wire(monkeypatch, FakeRepo(stored={}), part_vocab=[], learned=PART_WORDS)

    payload = get_milestone(client)

    assert completed_steps(payload) == []


def test_current_step_is_the_lowest_incomplete(client, monkeypatch):
    wire(monkeypatch, FakeRepo(stored={1: TRAINER_DONE_AT, 2: TRAINER_DONE_AT}))

    payload = get_milestone(client)

    assert payload["current_step"] == 3


def test_stored_timestamps_are_reported_and_derived_ones_are_null(client, monkeypatch):
    wire(monkeypatch, FakeRepo(stored={}, trainer_completed_at=TRAINER_DONE_AT))

    steps = {s["step"]: s["completed_at"] for s in get_milestone(client)["steps"]}

    assert steps[6] == TRAINER_DONE_AT.isoformat()
    assert steps[1] is None, "a filled-in step has no timestamp to report"


def test_get_requires_a_passage_id(client, monkeypatch):
    wire(monkeypatch, FakeRepo())
    assert client.get("/api/lesson/milestone").status_code == 400


# ---------------------------------------------------------------------------
# POST — passive steps only, idempotent
# ---------------------------------------------------------------------------

def post_step(client, step, passage_id=PASSAGE):
    return client.post(
        "/api/lesson/milestone", json={"passage_id": passage_id, "step": step}
    )


@pytest.mark.parametrize("step", [1, 2, 4, 5])
def test_post_records_a_passive_step_and_returns_the_new_state(client, monkeypatch, step):
    repo = FakeRepo()
    wire(monkeypatch, repo)

    response = post_step(client, step)

    assert response.status_code == 200
    assert repo.writes == [step]
    assert step in completed_steps(response.get_json())


@pytest.mark.parametrize("step", [3, 6])
def test_post_refuses_the_graded_steps(client, monkeypatch, step):
    """Their trainers already record them; accepting here would double-write."""
    repo = FakeRepo()
    wire(monkeypatch, repo)

    response = post_step(client, step)

    assert response.status_code == 400
    assert repo.writes == []


def test_post_is_idempotent_and_keeps_the_first_timestamp(client, monkeypatch):
    repo = FakeRepo()
    wire(monkeypatch, repo)

    post_step(client, 1)
    first = repo.stored[1]
    post_step(client, 1)

    assert repo.stored[1] == first, "ON CONFLICT DO NOTHING must not move completed_at"


@pytest.mark.parametrize("step", [0, 7, "x", None])
def test_post_rejects_an_out_of_range_step(client, monkeypatch, step):
    repo = FakeRepo()
    wire(monkeypatch, repo)

    assert post_step(client, step).status_code == 400
    assert repo.writes == []


def test_post_requires_a_passage_id(client, monkeypatch):
    wire(monkeypatch, FakeRepo())
    response = client.post("/api/lesson/milestone", json={"step": 1})
    assert response.status_code == 400
