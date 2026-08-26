import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from entity import validation as v


class FakeError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# require_str
# ---------------------------------------------------------------------------

def test_require_str_trims_and_returns():
    assert v.require_str(FakeError, "cn", "  hello  ") == "hello"


@pytest.mark.parametrize("value", [None, "", "   ", 123, {"a": 1}, ["x"], True])
def test_require_str_rejects_missing_or_wrong_type(value):
    with pytest.raises(FakeError):
        v.require_str(FakeError, "cn", value)


def test_require_str_enforces_max_len():
    with pytest.raises(FakeError):
        v.require_str(FakeError, "cn", "x" * 101, max_len=100)
    assert v.require_str(FakeError, "cn", "x" * 100, max_len=100) == "x" * 100


# ---------------------------------------------------------------------------
# optional_str
# ---------------------------------------------------------------------------

def test_optional_str_allows_none():
    assert v.optional_str(FakeError, "pinyin", None) is None


def test_optional_str_empty_string_becomes_none():
    assert v.optional_str(FakeError, "pinyin", "   ") is None


@pytest.mark.parametrize("value", [123, {"a": 1}, ["x"], True])
def test_optional_str_rejects_wrong_type(value):
    with pytest.raises(FakeError):
        v.optional_str(FakeError, "pinyin", value)


def test_optional_str_enforces_max_len():
    with pytest.raises(FakeError):
        v.optional_str(FakeError, "pinyin", "x" * 101, max_len=100)


# ---------------------------------------------------------------------------
# require_int / optional_int
# ---------------------------------------------------------------------------

def test_require_int_coerces_numeric_string():
    assert v.require_int(FakeError, "level", "3") == 3


@pytest.mark.parametrize("value", [None, "abc", True, False, {"a": 1}])
def test_require_int_rejects_non_numeric_and_bool(value):
    with pytest.raises(FakeError):
        v.require_int(FakeError, "level", value)


def test_optional_int_allows_none_and_empty_string():
    assert v.optional_int(FakeError, "level", None) is None
    assert v.optional_int(FakeError, "level", "") is None


def test_optional_int_rejects_wrong_type_when_present():
    with pytest.raises(FakeError):
        v.optional_int(FakeError, "level", "abc")


# ---------------------------------------------------------------------------
# require_one_of / optional_one_of
# ---------------------------------------------------------------------------

def test_require_one_of_accepts_member():
    assert v.require_one_of(FakeError, "category", "practice", {"practice", "exam"}) == "practice"


def test_require_one_of_rejects_non_member_with_readable_message():
    with pytest.raises(FakeError) as exc:
        v.require_one_of(FakeError, "category", "bogus", {"practice", "exam"})
    assert "practice" in str(exc.value)


def test_require_one_of_works_with_int_choices():
    """Regression: the error message must not crash joining non-string choices."""
    assert v.require_one_of(FakeError, "type", 2, {1, 2, 3}) == 2
    with pytest.raises(FakeError):
        v.require_one_of(FakeError, "type", 9, {1, 2, 3})


def test_optional_one_of_allows_none_and_empty_string():
    assert v.optional_one_of(FakeError, "hsk_level", None, {"HSK1"}) is None
    assert v.optional_one_of(FakeError, "hsk_level", "", {"HSK1"}) is None


# ---------------------------------------------------------------------------
# optional_dict / optional_list
# ---------------------------------------------------------------------------

def test_optional_dict_allows_none_and_rejects_wrong_type():
    assert v.optional_dict(FakeError, "options", None) is None
    assert v.optional_dict(FakeError, "options", {"a": 1}) == {"a": 1}
    with pytest.raises(FakeError):
        v.optional_dict(FakeError, "options", ["a"])
    with pytest.raises(FakeError):
        v.optional_dict(FakeError, "options", "not a dict")


def test_optional_list_allows_none_and_rejects_wrong_type():
    assert v.optional_list(FakeError, "tokens", None) is None
    assert v.optional_list(FakeError, "tokens", ["a", "b"]) == ["a", "b"]
    with pytest.raises(FakeError):
        v.optional_list(FakeError, "tokens", {"a": 1})
    with pytest.raises(FakeError):
        v.optional_list(FakeError, "tokens", "not a list")
