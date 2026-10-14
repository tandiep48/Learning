import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from entity.translation.entity import Translation
from entity.translation.repository import TranslationRepository


def _sqlite_session() -> Session:
    """In-memory SQLite with a split_part() shim so the repo's Postgres order_by
    (cast(split_part(id, '_', 3), Integer)) still runs under SQLite."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _register(dbapi_conn, _record):  # noqa: ANN001
        dbapi_conn.create_function(
            "split_part",
            3,
            lambda s, delim, n: (s.split(delim)[n - 1] if len(s.split(delim)) >= n else ""),
        )

    Translation.__table__.create(engine)
    return Session(engine)


def test_prefix_matches_only_its_lesson_not_sibling_lessons():
    """Regression: the prefix underscores must be literal, not LIKE single-char
    wildcards. "H2_2_" must not drag in H2_20_*, H2_21_* (same first digit)."""
    session = _sqlite_session()
    try:
        session.add_all(
            [
                Translation(translation_id="H2_2_1", cn="a", vn="a", en="a"),
                Translation(translation_id="H2_2_2", cn="b", vn="b", en="b"),
                Translation(translation_id="H2_2_10", cn="c", vn="c", en="c"),
                # Sibling lessons the unescaped "_" wildcard used to swallow.
                Translation(translation_id="H2_20_1", cn="x", vn="x", en="x"),
                Translation(translation_id="H2_21_1", cn="y", vn="y", en="y"),
                Translation(translation_id="H2_1_1", cn="z", vn="z", en="z"),
            ]
        )
        session.commit()

        rows = TranslationRepository(session).get_by_translation_id_prefix("H2_2_")
        ids = [r.translation_id for r in rows]
    finally:
        session.close()

    # Only lesson 2's rows, ordered by the trailing index numerically (10 after 2).
    assert ids == ["H2_2_1", "H2_2_2", "H2_2_10"]
