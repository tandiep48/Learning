"""
entity/translation/repository.py
-----------------------------------
All database queries for the `translation` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from sqlalchemy import select, func, cast, Integer
from sqlalchemy.orm import Session

from entity.translation.entity import Translation


class TranslationRepository:
    """Encapsulates all read operations for the Translation entity."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_by_translation_id_prefix(self, prefix: str) -> list[Translation]:
        """
        Every translation row whose translation_id starts with `prefix`
        (e.g. "H1_2_"), ordered by the trailing numeric index so H1_2_10
        follows H1_2_9, not H1_2_1.

        `startswith(autoescape=True)` is used rather than a raw `LIKE prefix + "%"`:
        the underscores in an id prefix like "H2_2_" are LIKE single-character
        wildcards, so "H2_2_%" would also match H2_20_*, H2_21_* … — every lesson
        sharing the first digit. autoescape escapes them so the prefix is literal.
        """
        return (
            self.session.execute(
                select(Translation)
                .where(Translation.translation_id.startswith(prefix, autoescape=True))
                .order_by(cast(func.split_part(Translation.translation_id, "_", 3), Integer))
            )
            .scalars()
            .all()
        )
