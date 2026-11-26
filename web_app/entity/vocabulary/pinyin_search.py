"""
Tone- and space-insensitive pinyin matching: "nihao" and "ni hao" find "nǐ hǎo".

The same folding is applied to the typed term (in Python) and to the stored column
(in SQL via translate(), so no database extension is needed).
"""

import unicodedata

from sqlalchemy import func

_PLAIN_TO_ACCENTED = {
    "a": "āáǎàâ",
    "e": "ēéěèê",
    "i": "īíǐìî",
    "o": "ōóǒòô",
    # ü has no key on most keyboards, so it matches both "u" and "v".
    "u": "ūúǔùûüǖǘǚǜv",
    "n": "ńňǹ",
    "m": "ḿ",
}
# Syllable separators, dropped from both sides.
_SEPARATORS = " '’-"

_FROM = "".join(_PLAIN_TO_ACCENTED.values())
_TO = "".join(plain * len(accented) for plain, accented in _PLAIN_TO_ACCENTED.items())
_TABLE = str.maketrans(_FROM, _TO, _SEPARATORS)


def fold_pinyin(text: str) -> str:
    """Lower-case `text` and strip its tone marks and syllable separators."""
    return unicodedata.normalize("NFC", text).lower().translate(_TABLE)


def folded_pinyin_column(column):
    """SQL expression applying fold_pinyin's folding to `column`."""
    # translate() deletes the characters of `from` that have no partner in `to`.
    return func.translate(func.lower(column), _FROM + _SEPARATORS, _TO)
