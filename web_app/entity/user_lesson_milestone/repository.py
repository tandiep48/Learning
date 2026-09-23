"""
entity/user_lesson_milestone/repository.py
-------------------------------------------
Queries and mutations for the six-step lesson milestone
(yi-chinese-manage/docs/plans/dashboard-tabs.md §10).

No raw SQL — everything goes through the ORM session. Session lifecycle
(commit/rollback/remove) is owned by the service layer.
"""

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from entity.user_lesson_milestone.entity import UserLessonMilestone
from entity.user_lesson_part_progress.entity import UserLessonPartProgress


class MilestoneRepository:
    """Encapsulates all queries/mutations for a part's milestone steps."""

    def __init__(self, session: Session):
        self.session = session

    def get_completed_steps(self, user_id, passage_id):
        """{step: completed_at} for every stored step of this (user, part)."""
        rows = self.session.execute(
            select(UserLessonMilestone.step, UserLessonMilestone.completed_at).where(
                UserLessonMilestone.user_id == user_id,
                UserLessonMilestone.passage_id == passage_id,
            )
        ).all()
        return {int(step): completed_at for step, completed_at in rows}

    def mark_step(self, user_id, passage_id, step):
        """Record one completed step.

        ON CONFLICT DO NOTHING, not DO UPDATE: any step may be replayed, and a
        replay must leave the original completed_at alone.
        """
        stmt = pg_insert(UserLessonMilestone).values(
            user_id=user_id,
            passage_id=passage_id,
            step=step,
            # Set explicitly rather than leaning on the column DEFAULT, so the
            # write does not depend on the table being created with one.
            completed_at=func.current_timestamp(),
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                UserLessonMilestone.user_id,
                UserLessonMilestone.passage_id,
                UserLessonMilestone.step,
            ]
        )
        self.session.execute(stmt)

    def get_lesson_trainer_completed_at(self, user_id, passage_id):
        """When the lesson trainer was passed for this part, or None.

        This is the authoritative source for step 6 — `mark_lesson_part_completed`
        only stamps it at or above the pass threshold — so the milestone reads it
        rather than trusting a stored row.
        """
        row = self.session.execute(
            select(UserLessonPartProgress.lesson_trainer_completed_at).where(
                UserLessonPartProgress.user_id == user_id,
                UserLessonPartProgress.passage_id == passage_id,
            )
        ).first()
        return row[0] if row else None
