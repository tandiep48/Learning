"""
entity/translation/service.py
--------------------------------
Business logic for looking up lesson translations.

Manages the SQLAlchemy session lifecycle and shapes repository rows into
the plain dicts callers expect.
"""

from entity.database import SessionLocal
from entity.translation.repository import TranslationRepository


def get_lesson_translations(hsk_level, lesson) -> list[dict]:
    """
    Return every translation row for one lesson, e.g. HSK1 + lesson 2 ->
    prefix "H1_2_". Ordered by the trailing index numerically so H1_2_10
    follows H1_2_9, not H1_2_1.
    """
    digits = "".join(ch for ch in str(hsk_level or "") if ch.isdigit())
    lesson_num = "".join(ch for ch in str(lesson or "") if ch.isdigit())
    if not digits or not lesson_num:
        return []
    prefix = f"H{digits}_{lesson_num}_"

    session = SessionLocal()
    try:
        rows = TranslationRepository(session).get_by_translation_id_prefix(prefix)
        return [
            {"translation_id": t.translation_id, "cn": t.cn, "vn": t.vn, "en": t.en}
            for t in rows
        ]
    finally:
        SessionLocal.remove()
