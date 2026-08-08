"""
db/content.py
--------------
Read queries for lesson/passage content — passage summaries, lesson
translations, passage lines, course vocabulary, vocab lessons, passage
vocabulary and grammar.
Extracted from the former monolithic db.py.
"""

from sqlalchemy import select, func, distinct, cast, and_, Integer
from sqlalchemy.orm import aliased

from entity.database import SessionLocal
from entity.passage.entity import LessonPassage
from entity.lesson_line.entity import LessonLine
from entity.vocabulary.entity import Vocabulary
from entity.passage_vocabulary.entity import PassageVocabulary
from entity.record.entity import VocabRecord
from entity.translation.entity import Translation
from entity.grammar_rule.entity import GrammarRule
from entity.grammar_context.entity import GrammarContext


def get_passages_summary(conn, hsk_level=None):
    if not conn:
        return []
    session = SessionLocal()
    try:
        q = (
            select(
                LessonPassage.passage_id,
                LessonPassage.hsk_level,
                func.count(LessonLine.id).label("line_count"),
            )
            .select_from(LessonPassage)
            .outerjoin(LessonLine, LessonPassage.passage_id == LessonLine.passage_id)
        )
        if hsk_level:
            q = q.where(LessonPassage.hsk_level == hsk_level)
        q = q.group_by(LessonPassage.passage_id, LessonPassage.hsk_level).order_by(
            LessonPassage.passage_id
        )
        rows = session.execute(q).all()
        return [{"passage_id": r[0], "hsk_level": r[1], "line_count": r[2]} for r in rows]
    finally:
        SessionLocal.remove()


def get_lesson_translations(conn, hsk_level, lesson):
    """Return every translation row for one lesson, e.g. HSK1 + lesson 2 -> 'H1_2_%'.
    Ordered by the trailing index numerically so H1_2_10 follows H1_2_9, not H1_2_1."""
    if not conn:
        return []
    digits = "".join(ch for ch in str(hsk_level or "") if ch.isdigit())
    lesson_num = "".join(ch for ch in str(lesson or "") if ch.isdigit())
    if not digits or not lesson_num:
        return []
    prefix = f"H{digits}_{lesson_num}_"

    session = SessionLocal()
    try:
        rows = session.execute(
            select(Translation.translation_id, Translation.cn, Translation.vn, Translation.en)
            .where(Translation.translation_id.like(prefix + "%"))
            .order_by(cast(func.split_part(Translation.translation_id, "_", 3), Integer))
        ).all()
        return [{"translation_id": r[0], "cn": r[1], "vn": r[2], "en": r[3]} for r in rows]
    finally:
        SessionLocal.remove()


def get_passage_content(conn, passage_id):
    if not conn:
        return None
    session = SessionLocal()
    try:
        hsk_level = session.execute(
            select(LessonPassage.hsk_level).where(LessonPassage.passage_id == passage_id)
        ).scalar_one_or_none()
        if hsk_level is None and not session.execute(
            select(LessonPassage.passage_id).where(LessonPassage.passage_id == passage_id)
        ).first():
            return None

        rows = session.execute(
            select(
                LessonLine.line_id, LessonLine.speaker, LessonLine.content, LessonLine.pinyin,
                LessonLine.audio_key, LessonLine.translation_en, LessonLine.translation_vi,
                LessonLine.tokens, LessonLine.flag,
            )
            .where(LessonLine.passage_id == passage_id)
            .order_by(LessonLine.line_id)
        ).all()
        lines = [
            {
                "line_id": r[0],
                "speaker": r[1],
                "content": r[2],
                "pinyin": r[3],
                "audio_key": r[4],
                "translations": {"en": r[5], "vi": r[6]},
                "tokens": r[7] if r[7] else [],
                "flag": 1 if r[8] is None else r[8],
            }
            for r in rows
        ]
        return {"passage_id": passage_id, "hsk_level": hsk_level, "lines": lines}
    finally:
        SessionLocal.remove()


def get_course_vocab(conn):
    import pandas as pd
    if not conn:
        return pd.DataFrame()
    session = SessionLocal()
    try:
        rows = session.execute(
            select(
                Vocabulary.cn, Vocabulary.pinyin, Vocabulary.meaning_vn,
                Vocabulary.meaning_en, Vocabulary.audio_key, Vocabulary.hsk_level,
            ).order_by(Vocabulary.hsk_level, Vocabulary.id)
        ).all()
        return pd.DataFrame(
            [tuple(r) for r in rows],
            columns=["word", "pinyin", "meaning_vn", "meaning_en", "audio_key", "level"],
        )
    finally:
        SessionLocal.remove()


def has_vocab_history(conn, user_id):
    """Returns True if the user has any vocab_records entries."""
    if not conn:
        return False
    session = SessionLocal()
    try:
        return session.execute(
            select(VocabRecord.id).where(VocabRecord.user_id == user_id).limit(1)
        ).first() is not None
    except Exception as e:
        print(f"⚠️ Database query failed (has_vocab_history): {e}")
        return False
    finally:
        SessionLocal.remove()


def get_vocab_lessons(conn, hsk_level, lesson_size=10):
    """
    Returns a list of lesson groups for a given HSK level.
    Each lesson contains lesson_size words.
    Returns: [{lesson: 1, start_idx: 0, end_idx: 9, word_count: 10, preview: ['你','好',...]}, ...]
    """
    if not conn:
        return []
    session = SessionLocal()
    try:
        words = [
            r[0]
            for r in session.execute(
                select(Vocabulary.cn).where(Vocabulary.hsk_level == hsk_level).order_by(Vocabulary.id)
            ).all()
        ]
        lessons = []
        for i in range(0, len(words), lesson_size):
            chunk = words[i:i + lesson_size]
            lessons.append({
                "lesson": (i // lesson_size) + 1,
                "start_idx": i,
                "end_idx": i + len(chunk) - 1,
                "word_count": len(chunk),
                "preview": chunk[:4],  # first 4 words as preview
            })
        return lessons
    except Exception as e:
        print(f"⚠️ Database query failed (get_vocab_lessons): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_all_vn_meanings(conn):
    if not conn:
        return []
    session = SessionLocal()
    try:
        rows = session.execute(
            select(distinct(Vocabulary.meaning_vn)).where(
                Vocabulary.meaning_vn.isnot(None), Vocabulary.meaning_vn != ""
            )
        ).all()
        return [r[0] for r in rows]
    finally:
        SessionLocal.remove()


def get_passage_vocab(conn, passage_id):
    """Return vocabulary words linked to a passage via passage_vocabulary."""
    if not conn:
        return []
    session = SessionLocal()
    try:
        rows = session.execute(
            select(
                Vocabulary.cn, Vocabulary.pinyin, Vocabulary.meaning_vn,
                Vocabulary.meaning_en, Vocabulary.audio_key, Vocabulary.hsk_level,
            )
            .select_from(PassageVocabulary)
            .join(Vocabulary, Vocabulary.cn == PassageVocabulary.cn)
            .where(PassageVocabulary.passage_id == passage_id)
            .order_by(Vocabulary.cn)
        ).all()
        return [
            {
                "cn": r[0],
                "pinyin": r[1] or "",
                "meaning_vn": r[2] or "",
                "meaning_en": r[3] or "",
                "audio_key": r[4] or "",
                "hsk_level": r[5] or "",
            }
            for r in rows
        ]
    finally:
        SessionLocal.remove()


def get_grammar_for_lesson(conn, hsk_level, lesson):
    """All grammar rules for a whole lesson (every part), ordered by insertion id.
    The caller splits the flat list into sections at each type=1 row."""
    session = SessionLocal()
    try:
        prefix = f"H{hsk_level}-{lesson}-%"
        c_vn = aliased(GrammarContext)
        c_en = aliased(GrammarContext)
        rows = session.execute(
            select(
                GrammarRule.grammar_id,
                GrammarRule.type,
                GrammarRule.vietnamese_content,
                GrammarRule.english_content,
                c_vn.content_json.label("vn_context"),
                c_en.content_json.label("en_context"),
            )
            .select_from(GrammarRule)
            .outerjoin(c_vn, and_(GrammarRule.vietnamese_content == c_vn.grammar_id, GrammarRule.type == 4))
            .outerjoin(c_en, and_(GrammarRule.english_content == c_en.grammar_id, GrammarRule.type == 4))
            .where(GrammarRule.grammar_id.like(prefix))
            .order_by(GrammarRule.id.asc())
        ).all()
        cols = ["grammar_id", "type", "vietnamese_content", "english_content", "vn_context", "en_context"]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get("vn_context") is None:
                d.pop("vn_context", None)
            if d.get("en_context") is None:
                d.pop("en_context", None)
            results.append(d)
        return results
    except Exception as e:
        print(f"[WARN] get_grammar_for_lesson failed: {e}")
        return []
    finally:
        SessionLocal.remove()
