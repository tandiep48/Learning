import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from entity.passage.entity import LessonPassage
from entity.passage.repository import PassageRepository


def _sqlite_session() -> Session:
    engine = create_engine("sqlite://")
    LessonPassage.__table__.create(engine)
    return Session(engine)


def test_prefix_matches_only_its_lesson_not_sibling_lessons():
    """Regression: the prefix underscores must be literal, not LIKE single-char
    wildcards. 'H1_2_' must not drag in H1_20_*, H1_21_* (same first digit)."""
    session = _sqlite_session()
    try:
        session.add_all(
            [
                LessonPassage(passage_id="H1_2_1"),
                LessonPassage(passage_id="H1_2_2"),
                # Sibling lessons the unescaped "_" wildcard used to swallow.
                LessonPassage(passage_id="H1_20_1"),
                LessonPassage(passage_id="H1_21_1"),
                LessonPassage(passage_id="H1_1_1"),
            ]
        )
        session.commit()

        ids = PassageRepository(session).get_ids_by_prefix("H1_2_")
    finally:
        session.close()

    assert ids == ["H1_2_1", "H1_2_2"]
