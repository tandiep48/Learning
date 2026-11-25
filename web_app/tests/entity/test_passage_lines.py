"""Lesson line editing rules, run against an in-memory SQLite database."""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from entity.lesson_line.entity import LessonLine
from entity.passage import service
from entity.passage.entity import LessonPassage
from entity.passage.service import PassageServiceError


@compiles(JSONB, "sqlite")
def _jsonb_as_json(element, compiler, **kw):
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    LessonPassage.__table__.create(engine)
    LessonLine.__table__.create(engine)
    with patch.object(service, "SessionLocal", scoped_session(sessionmaker(bind=engine))):
        service.create_passage({
            "passage_id": "H1_1_1",
            "hsk_level": "HSK1",
            "lines": [
                {"line_id": 1, "content": "你好！", "audio_key": "H1_1_1_1", "tokens": ["你", "好", "！"], "flag": 0},
                {"line_id": 2, "content": "再见", "audio_key": "H1_1_1_2", "tokens": ["再见"]},
            ],
        })
        yield service


# ---------------------------------------------------------------------------
# flag
# ---------------------------------------------------------------------------

def test_flag_survives_a_read_and_replace_round_trip(db):
    lines = db.get_passage("H1_1_1")["lines"]
    assert [line["flag"] for line in lines] == [0, 1]

    db.update_passage("H1_1_1", {"lines": lines})

    assert [line["flag"] for line in db.get_passage("H1_1_1")["lines"]] == [0, 1]


def test_update_line_changes_flag(db):
    assert db.update_passage_line("H1_1_1", 2, {"flag": 0})["flag"] == 0


@pytest.mark.parametrize("flag", [2, None, "1"])
def test_update_line_rejects_unknown_flag(db, flag):
    with pytest.raises(PassageServiceError):
        db.update_passage_line("H1_1_1", 1, {"flag": flag})


# ---------------------------------------------------------------------------
# tokens must match content
# ---------------------------------------------------------------------------

def test_content_change_with_stale_tokens_is_rejected(db):
    with pytest.raises(PassageServiceError, match="does not match"):
        db.update_passage_line("H1_1_1", 1, {"content": "您好！"})

    assert db.get_passage_line("H1_1_1", 1)["content"] == "你好！"


def test_tokens_may_omit_punctuation(db):
    line = db.update_passage_line("H1_1_1", 1, {"content": "您好！", "tokens": ["您", "好"]})

    assert line["tokens"] == ["您", "好"]


def test_empty_tokens_are_allowed(db):
    assert db.update_passage_line("H1_1_1", 1, {"content": "您好", "tokens": []})["tokens"] == []


@pytest.mark.parametrize("tokens", [["再"], ["再见", ""], [1]])
def test_bad_tokens_are_rejected(db, tokens):
    with pytest.raises(PassageServiceError):
        db.update_passage_line("H1_1_1", 2, {"tokens": tokens})


def test_add_line_rejects_mismatched_tokens(db):
    with pytest.raises(PassageServiceError):
        db.add_passage_line("H1_1_1", {"line_id": 3, "content": "好", "tokens": ["坏"]})


def test_older_mismatched_line_can_still_edit_other_fields(db):
    db.update_passage("H1_1_1", {"lines": [{"line_id": 1, "content": "好", "tokens": ["坏"]}]})

    line = db.update_passage_line(
        "H1_1_1", 1, {"content": "好", "tokens": ["坏"], "translation_en": "Good"}
    )

    assert line["translation_en"] == "Good"


# ---------------------------------------------------------------------------
# duplicate line numbers
# ---------------------------------------------------------------------------

def test_replacing_lines_with_a_repeated_number_is_a_conflict(db):
    with pytest.raises(PassageServiceError) as caught:
        db.update_passage("H1_1_1", {"lines": [{"line_id": 1}, {"line_id": 1}]})

    assert caught.value.status_code == 409
    assert len(db.get_passage("H1_1_1")["lines"]) == 2


def test_creating_a_passage_with_a_repeated_number_is_a_conflict(db):
    with pytest.raises(PassageServiceError, match="more than once"):
        db.create_passage({"passage_id": "H1_1_2", "lines": [{"line_id": 3}, {"line_id": 3}]})


# ---------------------------------------------------------------------------
# passage titles
# ---------------------------------------------------------------------------

def test_update_passage_titles_leaves_lines_alone(db):
    result = db.update_passage("H1_1_1", {"title_en": " Greetings ", "title_vn": ""})

    assert (result["title_en"], result["title_vn"]) == ("Greetings", None)
    assert len(result["lines"]) == 2


def test_update_passage_rejects_a_long_title(db):
    with pytest.raises(PassageServiceError):
        db.update_passage("H1_1_1", {"title_en": "x" * 256})
