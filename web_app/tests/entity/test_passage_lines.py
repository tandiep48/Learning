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
