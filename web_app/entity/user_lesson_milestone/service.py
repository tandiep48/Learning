"""
entity/user_lesson_milestone/service.py
----------------------------------------
Business logic for the six-step lesson milestone
(yi-chinese-manage/docs/plans/dashboard-tabs.md §10).

The design rule that shapes this whole module: **the two graded steps are
derived, never trusted from the milestone table alone.** Their authoritative
sources already exist and are what mastery and the lesson picker read, so
deriving them is what keeps the milestone from drifting out of step with the
rest of the app:

    step 3 (vocab trainer)  -> every word of the part is mastered
    step 6 (lesson trainer) -> user_lesson_part_progress.lesson_trainer_completed_at

Effective completion is `stored OR derived`, plus every step below the highest
completed one — finishing the lesson trainer implies the learner walked the path
to get there. That last rule is also the entire backfill story: a learner who
finished a part before this shipped opens it and sees 6/6 with no stored rows,
so there is no migration script and no data backfill.

Manages the SQLAlchemy session lifecycle and returns plain dicts.
"""

from entity.database import SessionLocal
from entity.user_lesson_milestone.repository import MilestoneRepository
from entity.passage_vocabulary.service import get_passage_vocab
from entity.record.service import get_learned_words

TOTAL_STEPS = 6

# Steps the learner completes by pressing Continue. The graded steps (3, 6) are
# recorded by the trainers' own endpoints and are rejected by the POST route, so
# the milestone can never double-write them.
PASSIVE_STEPS = (1, 2, 4, 5)

VOCAB_TRAINER_STEP = 3
LESSON_TRAINER_STEP = 6


def is_passive_step(step):
    return step in PASSIVE_STEPS


def _part_words_all_mastered(user_id, passage_id):
    """True when every curated word of the part is fully learned.

    A part with no vocab is not "mastered" — an empty set would otherwise make
    step 3 vacuously complete for book parts and the Numbers pseudo-part.
    """
    vocab = get_passage_vocab(passage_id) or []
    words = {row.get("cn") for row in vocab if row.get("cn")}
    if not words:
        return False
    return words.issubset(set(get_learned_words(user_id)))


def get_milestone(user_id, passage_id):
    """The milestone state for one part, in the shape GET /api/lesson/milestone returns."""
    session = SessionLocal()
    try:
        repo = MilestoneRepository(session)
        stored = repo.get_completed_steps(user_id, passage_id)
        trainer_completed_at = repo.get_lesson_trainer_completed_at(user_id, passage_id)
    except Exception as e:
        print(f"⚠️ Database get_milestone failed: {e}")
        stored, trainer_completed_at = {}, None
    finally:
        SessionLocal.remove()

    # {step: completed_at or None}
    effective = dict(stored)

    if trainer_completed_at is not None:
        effective.setdefault(LESSON_TRAINER_STEP, trainer_completed_at)

    # Only worth the vocab + mastery reads when the step isn't already known.
    if VOCAB_TRAINER_STEP not in effective and _part_words_all_mastered(user_id, passage_id):
        effective.setdefault(VOCAB_TRAINER_STEP, None)

    # Everything below the highest completed step counts as walked.
    if effective:
        for step in range(1, max(effective) + 1):
            effective.setdefault(step, None)

    steps = [
        {
            "step": step,
            "completed": step in effective,
            "completed_at": (
                effective[step].isoformat()
                if step in effective and effective[step] is not None
                else None
            ),
        }
        for step in range(1, TOTAL_STEPS + 1)
    ]

    incomplete = [s["step"] for s in steps if not s["completed"]]
    current_step = incomplete[0] if incomplete else TOTAL_STEPS + 1

    return {
        "passage_id": passage_id,
        "total_steps": TOTAL_STEPS,
        "current_step": current_step,
        "steps": steps,
    }


def mark_milestone_step(user_id, passage_id, step):
    """Record one completed step. Idempotent — a replay keeps the first timestamp."""
    session = SessionLocal()
    try:
        MilestoneRepository(session).mark_step(user_id, passage_id, step)
        session.commit()
        return True
    except Exception as e:
        print(f"⚠️ Database mark_milestone_step failed: {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()
