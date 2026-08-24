"""
entity/chinese_stroke_info/repository.py
-------------------------------------------
All database queries for the `chinese_stroke_info` table using SQLAlchemy.

No raw SQL strings — all queries go through the ORM session.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from entity.chinese_stroke_info.entity import ChineseStrokeInfo


class ChineseStrokeInfoRepository:
    """Encapsulates all read operations for the ChineseStrokeInfo entity."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_by_cn(self, cn: str) -> Optional[ChineseStrokeInfo]:
        """Return a single ChineseStrokeInfo by Chinese word (primary key), or None."""
        return self.session.get(ChineseStrokeInfo, cn)

    def get_by_words(self, words: list[str]) -> list[ChineseStrokeInfo]:
        """ChineseStrokeInfo rows whose `cn` is in `words`."""
        if not words:
            return []
        return (
            self.session.execute(
                select(ChineseStrokeInfo).where(ChineseStrokeInfo.cn.in_(words))
            )
            .scalars()
            .all()
        )
