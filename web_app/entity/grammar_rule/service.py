"""
entity/grammar_rule/service.py
---------------------------------
Business logic for looking up a lesson's grammar rules.

Manages the SQLAlchemy session lifecycle and shapes repository rows into
the plain dicts callers expect.
"""

from entity.database import SessionLocal
from entity.grammar_rule.repository import GrammarRuleRepository

_COLUMNS = ["grammar_id", "type", "vietnamese_content", "english_content", "vn_context", "en_context"]


def get_grammar_for_lesson(hsk_level, lesson) -> list[dict]:
    """
    All grammar rules for a whole lesson (every part), ordered by insertion
    id. The caller splits the flat list into sections at each type=1 row.
    """
    session = SessionLocal()
    try:
        pattern = f"H{hsk_level}-{lesson}-%"
        rows = GrammarRuleRepository(session).get_rules_for_lesson(pattern)
        results = []
        for row in rows:
            d = dict(zip(_COLUMNS, row))
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
