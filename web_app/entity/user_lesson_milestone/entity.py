"""
entity/user_lesson_milestone/entity.py
--------------------------------------------
SQLAlchemy ORM model for the `user_lesson_milestone` table — one row per step a
user has completed in a lesson part's six-step milestone (see
yi-chinese-manage/docs/plans/dashboard-tabs.md §10).

Deliberately append-only: a row records *that* a step was completed and when.
Replaying a step must not move the original timestamp, so writes are
ON CONFLICT DO NOTHING.

Steps 3 and 6 are never trusted from this table alone — they are derived from
the mastery data that already governs them (see repository.py). This table only
carries the passive steps that had nowhere else to live.
"""

from sqlalchemy import Column, BigInteger, String, SmallInteger, DateTime
from entity.database import Base


class UserLessonMilestone(Base):
    __tablename__ = "user_lesson_milestone"

    user_id = Column(BigInteger, primary_key=True)
    passage_id = Column(String, primary_key=True)
    step = Column(SmallInteger, primary_key=True)
    completed_at = Column(DateTime(timezone=True), nullable=False)
