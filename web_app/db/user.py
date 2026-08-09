"""
db/user.py
-----------
Queries for the `users` table — HSK level progression, profile/avatar,
hanzi font & script, UI language, password, and profile time summary.
Extracted from the former monolithic db.py.
"""

from sqlalchemy import select, update, func, distinct, cast, and_, Integer, BigInteger

from entity.database import SessionLocal
from entity.user.entity import User
from entity.passage.entity import LessonPassage
from entity.lesson_line.entity import LessonLine  # noqa: F401  (registers the mapper LessonPassage.lines references)
from entity.passage_vocabulary.entity import PassageVocabulary
from entity.user_lesson_part_progress.entity import UserLessonPartProgress
from entity.record.entity import VocabRecord, LessonRecord, PracticeRecord
from db.records import get_learned_words


def _level_passes(level, lesson_pct, word_pct):
    """Per-band pass rule for HSK level progression (see recompute_user_level)."""
    if level in (1, 2):
        return lesson_pct >= 85 or (word_pct >= 85 and lesson_pct >= 50)
    if level in (3, 4):
        return lesson_pct >= 80 or (word_pct >= 80 and lesson_pct >= 50)
    if level == 5:
        return lesson_pct >= 75 or (word_pct >= 75 and lesson_pct >= 40)
    if level == 6:
        return lesson_pct >= 70 or (word_pct >= 70 and lesson_pct >= 40)
    return False


def recompute_user_level(user_id):
    """
    Derive and (if higher) persist the user's HSK level from lesson-trainer progress.
    For each level compute lesson% (completed parts / total parts across ALL lessons at
    that level) and word% (mastered / total lesson words at that level), then apply the
    per-band pass rule in _level_passes. The user jumps to (highest passed level + 1),
    capped at HSK 6, and the level never decreases. Returns the resulting level.
    """
    session = SessionLocal()
    try:
        learned = get_learned_words(user_id)

        # Level number parsed from the passage_id prefix, e.g. "H1_2_3" -> 1.
        lvl = cast(
            func.regexp_replace(
                func.split_part(LessonPassage.passage_id, "_", 1), r"\D", "", "g"
            ),
            Integer,
        ).label("lvl")
        is_lesson_passage = LessonPassage.passage_id.op("~")(r"^H\d+_\d+_\d+$")

        # parts: total vs completed lesson-trainer parts per level.
        q_parts = (
            select(
                lvl,
                func.count().label("total_parts"),
                func.count(UserLessonPartProgress.passage_id).label("done_parts"),
            )
            .select_from(LessonPassage)
            .outerjoin(
                UserLessonPartProgress,
                and_(
                    UserLessonPartProgress.passage_id == LessonPassage.passage_id,
                    UserLessonPartProgress.user_id == user_id,
                    UserLessonPartProgress.lesson_trainer_completed_at.isnot(None),
                ),
            )
            .where(is_lesson_passage)
            .group_by(lvl)
        )
        parts = {}
        for row in session.execute(q_parts).all():
            if row.lvl:
                parts[row.lvl] = (row.total_parts or 0, row.done_parts or 0)

        # words: total vs mastered lesson words per level.
        q_words = (
            select(
                lvl,
                func.count(distinct(PassageVocabulary.cn)).label("total_words"),
                func.count(distinct(PassageVocabulary.cn))
                .filter(PassageVocabulary.cn.in_(learned))
                .label("mastered_words"),
            )
            .select_from(LessonPassage)
            .join(
                PassageVocabulary,
                PassageVocabulary.passage_id == LessonPassage.passage_id,
            )
            .where(is_lesson_passage)
            .group_by(lvl)
        )
        words = {}
        for row in session.execute(q_words).all():
            if row.lvl:
                words[row.lvl] = (row.total_words or 0, row.mastered_words or 0)

        current_row = session.execute(
            select(User.level).where(User.id == user_id)
        ).first()
        current = int(current_row[0]) if current_row and current_row[0] else 1

        highest_passed = 0
        for lv in range(1, 7):
            ptot, pdone = parts.get(lv, (0, 0))
            wtot, wdone = words.get(lv, (0, 0))
            lesson_pct = (pdone / ptot * 100) if ptot else 0
            word_pct = (wdone / wtot * 100) if wtot else 0
            if _level_passes(lv, lesson_pct, word_pct):
                highest_passed = lv

        target = min(6, highest_passed + 1) if highest_passed >= 1 else 1
        target = min(6, max(current, target))   # never decrease

        if target > current:
            session.execute(update(User).where(User.id == user_id).values(level=target))
            session.commit()
        return target
    except Exception as e:
        print(f"Database recompute_user_level failed: {e}")
        session.rollback()
        return None
    finally:
        SessionLocal.remove()


def update_user_avatar_path(user_id, avatar_path):
    session = SessionLocal()
    try:
        session.execute(update(User).where(User.id == user_id).values(avatar_path=avatar_path))
        session.commit()
        return True
    except Exception as e:
        print(f"⚠️ Database update_user_avatar_path failed: {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()


def _get_user_setting(user_id, column, default):
    """Shared helper for the COALESCE(NULLIF(col, ''), default) settings getters."""
    session = SessionLocal()
    try:
        val = session.execute(
            select(func.coalesce(func.nullif(column, ""), default)).where(User.id == user_id)
        ).scalar()
        return val if val is not None else default
    except Exception as e:
        print(f"Database get user setting failed ({column}): {e}")
        session.rollback()
        return default
    finally:
        SessionLocal.remove()


def _update_user_setting(user_id, **values):
    session = SessionLocal()
    try:
        session.execute(update(User).where(User.id == user_id).values(**values))
        session.commit()
        return True
    except Exception as e:
        print(f"Database update user setting failed ({list(values)}): {e}")
        session.rollback()
        return False
    finally:
        SessionLocal.remove()


def get_user_hanzi_font(user_id):
    return _get_user_setting(user_id, User.hanzi_font, "Noto Sans")


def update_user_hanzi_font(user_id, hanzi_font):
    return _update_user_setting(user_id, hanzi_font=hanzi_font)


def get_user_hanzi_script(user_id):
    return _get_user_setting(user_id, User.hanzi_script, "simplified")


def update_user_hanzi_script(user_id, hanzi_script):
    return _update_user_setting(user_id, hanzi_script=hanzi_script)


def get_user_ui_language(user_id):
    return _get_user_setting(user_id, User.ui_language, "en")


def update_user_ui_language(user_id, ui_language):
    return _update_user_setting(user_id, ui_language=ui_language)


def update_user_password(user_id, password_hash):
    return _update_user_setting(user_id, password=password_hash)


def get_profile_summary(user_id):
    summary = {
        "time_totals_ms": {"vocab": 0, "lesson": 0, "practice": 0, "exam": 0},
        "vocab_mode_time_ms": [],
        "lesson_mode_time_ms": [],
        "practice_skill_time_ms": []
    }

    session = SessionLocal()
    try:
        def _mode_time(model):
            return session.execute(
                select(
                    model.mode,
                    cast(func.coalesce(func.sum(model.response_time_ms), 0), BigInteger),
                )
                .where(model.user_id == user_id, model.response_time_ms.isnot(None))
                .group_by(model.mode)
                .order_by(model.mode)
            ).all()

        try:
            rows = _mode_time(VocabRecord)
            summary["vocab_mode_time_ms"] = [{"mode": r[0], "time_ms": int(r[1] or 0)} for r in rows]
            summary["time_totals_ms"]["vocab"] = sum(item["time_ms"] for item in summary["vocab_mode_time_ms"])
        except Exception as e:
            print(f"⚠️ Database vocab time summary failed: {e}")
            session.rollback()

        lesson_mode_names = {1: "meaning", 2: "typing", 3: "reorder", 4: "listening"}
        try:
            rows = _mode_time(LessonRecord)
            summary["lesson_mode_time_ms"] = [
                {"mode": lesson_mode_names.get(r[0], str(r[0])), "time_ms": int(r[1] or 0)}
                for r in rows
            ]
            summary["time_totals_ms"]["lesson"] = sum(item["time_ms"] for item in summary["lesson_mode_time_ms"])
        except Exception as e:
            print(f"⚠️ Database lesson time summary failed: {e}")
            session.rollback()

        try:
            category = func.coalesce(PracticeRecord.category, "practice").label("category")
            skill = func.coalesce(PracticeRecord.skill, "unknown").label("skill")
            rows = session.execute(
                select(
                    category,
                    skill,
                    cast(func.coalesce(func.sum(PracticeRecord.response_time_ms), 0), BigInteger),
                )
                .where(PracticeRecord.user_id == user_id, PracticeRecord.response_time_ms.isnot(None))
                .group_by(category, skill)
                .order_by(category, skill)
            ).all()
            summary["practice_skill_time_ms"] = [
                {"category": r[0], "skill": r[1], "time_ms": int(r[2] or 0)}
                for r in rows
            ]
            for item in summary["practice_skill_time_ms"]:
                cat = item["category"] if item["category"] in ("practice", "exam") else "practice"
                summary["time_totals_ms"][cat] += item["time_ms"]
        except Exception as e:
            print(f"⚠️ Database practice time summary failed: {e}")
            session.rollback()

        return summary
    finally:
        SessionLocal.remove()
