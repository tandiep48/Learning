import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.vocabulary.pinyin_search import fold_pinyin
from entity.vocabulary.repository import VocabRepository


@pytest.mark.parametrize("typed, stored", [
    ("nihao", "nǐ hǎo"),
    ("NI HAO", "Nǐhǎo"),
    ("nv er", "nǚ'ér"),
    ("nuer", "nǚ’ér"),
    ("lv", "lǜ"),
    ("zhongwen", "zhōng-wén"),
])
def test_typed_term_matches_stored_pinyin(typed, stored):
    assert fold_pinyin(typed) == fold_pinyin(stored)


def test_folds_decomposed_tone_marks():
    assert fold_pinyin("nǐ") == "ni"


def test_keeps_chinese_characters():
    assert fold_pinyin("你好") == "你好"


def _search_filter(term):
    """The SQL of the filter get_all applies for `term`."""
    session = MagicMock()
    VocabRepository(session).get_all(search=term)
    clause = session.query.return_value.filter.call_args.args[0]
    compiled = clause.compile(dialect=postgresql.dialect())
    return str(compiled), list(compiled.params.values())


def test_search_matches_word_or_folded_pinyin():
    sql, params = _search_filter("Nǐ hao")
    assert "vocabulary.cn ILIKE" in sql
    assert "translate(lower(vocabulary.pinyin)" in sql
    assert "%Nǐ hao%" in params
    assert "%nihao%" in params


def test_term_made_only_of_separators_does_not_match_all_pinyin():
    sql, _ = _search_filter("'")
    assert "pinyin" not in sql
