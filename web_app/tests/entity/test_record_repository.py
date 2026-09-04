import os
import sys
from unittest.mock import MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.record.repository import RecordRepository, PER_ANSWER_MS_CAP


def _compiled_sql(statement):
    """Render a Core statement to a SQL string with literals inlined, so the test can
    assert on the generated query without opening a real DB connection."""
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


def test_per_answer_ms_cap_is_five_minutes():
    assert PER_ANSWER_MS_CAP == 300_000


def test_get_time_learned_last_3_days_clamps_each_answer_to_the_cap():
    """The per-answer time must be clamped (least(coalesce(response_time_ms, 0), CAP))
    before summing, so one abandoned/idle task can't inflate a day's total."""
    session = MagicMock()
    RecordRepository(session).get_time_learned_last_3_days(1)

    statement = session.execute.call_args.args[0]
    sql = _compiled_sql(statement).lower()

    assert "least" in sql
    assert "coalesce" in sql
    assert str(PER_ANSWER_MS_CAP) in sql


def test_get_time_learned_last_3_days_sorts_rows_oldest_first():
    session = MagicMock()
    # The query fetches the 3 most recent days DESC; the method re-sorts them ascending.
    session.execute.return_value.all.return_value = [
        ("2026-07-25", 200),
        ("2026-07-24", 120),
    ]

    result = RecordRepository(session).get_time_learned_last_3_days(1)

    assert result == [("2026-07-24", 120), ("2026-07-25", 200)]
