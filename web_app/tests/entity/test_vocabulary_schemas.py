import os
import sys

import pytest
from pydantic import ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity.vocabulary.schemas import VocabQuery


def test_defaults_when_empty():
    q = VocabQuery()
    assert q.page == 1
    assert q.page_size == 20
    assert q.hsk_level is None
    assert q.search is None


def test_trims_search_and_blanks_to_none():
    assert VocabQuery(search="  hao  ").search == "hao"
    assert VocabQuery(search="   ").search is None


def test_blank_hsk_level_is_no_filter():
    assert VocabQuery(hsk_level="").hsk_level is None
    assert VocabQuery(hsk_level="HSK3").hsk_level == "HSK3"


@pytest.mark.parametrize("payload", [
    {"page": 0},
    {"page_size": 0},
    {"page_size": 101},
    {"hsk_level": "HSK9"},
    {"search": "x" * 101},
    {"unexpected": True},
])
def test_rejects_invalid_input(payload):
    with pytest.raises(ValidationError):
        VocabQuery(**payload)
