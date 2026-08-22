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
        """
        return (
            self.session.execute(
                select(Translation)
                .where(Translation.translation_id.like(prefix + "%"))
                .order_by(cast(func.split_part(Translation.translation_id, "_", 3), Integer))
            )
            .scalars()
            .all()
        )
