import importlib.util
import os
import sys

import openpyxl
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "scripts", "import_chinese_dict.py"
)
_spec = importlib.util.spec_from_file_location("import_chinese_dict", _SCRIPT)
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)


HEADER = [
    "id", "cn", "zh", "py", "audio_key", "freq", "pos", "vn", "en", "tags",
    "sematic_difficulty", "sematic_tags", "total_strokes_cn", "total_strokes_zh",
    "strokes_cn", "strokes_zh", "word_length", "strokes_difficult_cn",
    "strokes_difficult_cn_norm", "strokes_difficult_zh", "strokes_difficult_zh_norm",
    "corpus_count",
]


def write_sheet(path, rows):
    """Write a dictionary workbook holding `rows` (dicts of HEADER columns)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(HEADER)
    for row in rows:
        ws.append([row.get(name) for name in HEADER])
    wb.save(path)
    wb.close()


def test_load_rows_merges_senses_of_the_same_word(tmp_path):
    path = tmp_path / "dict.xlsx"
    write_sheet(path, [
        {"id": 1, "cn": "会", "py": "huì", "en": "can, to be able to",
         "vn": "biết", "tags": "h1, verb", "audio_key": "hui.mp3",
         "total_strokes_cn": 6, "word_length": 1},
        {"id": 2, "cn": "会", "py": "huì", "en": "will", "vn": "sẽ",
         "tags": "h5, verb", "audio_key": "ignored.mp3"},
        {"id": 3, "cn": "书", "py": "shū", "en": "book", "vn": "sách", "tags": "h1"},
    ])

    rows, merged = importer.load_rows(str(path))
    by_cn = {r["cn"]: r for r in rows}

    assert merged == 1
    assert len(rows) == 2
    assert by_cn["会"]["meaning_en"] == "can, to be able to; will"
    assert by_cn["会"]["meaning_vn"] == "biết; sẽ"
    # One pinyin, one audio key: repeated values collapse and the first row wins.
    assert by_cn["会"]["pinyin"] == "huì"
    assert by_cn["会"]["audio_key"] == "hui.mp3"
    # The word is taught at HSK1, so the later h5 tag must not raise its level.
    assert by_cn["会"]["hsk_level"] == "HSK1"
    assert by_cn["会"]["total_strokes_cn"] == 6
    assert by_cn["书"]["meaning_en"] == "book"


def test_load_rows_keeps_distinct_readings_and_ignores_blank_words(tmp_path):
    path = tmp_path / "dict.xlsx"
    write_sheet(path, [
        {"id": 1, "cn": "长", "py": "cháng", "en": "long", "vn": "dài"},
        # A trailing non-breaking space must not make this look like a new reading.
        {"id": 2, "cn": "长", "py": "zhǎng\xa0", "en": "grow", "vn": "lớn lên"},
        {"id": 3, "cn": "长", "py": "cháng", "en": "long", "vn": "dài"},
        {"id": 4, "cn": "   ", "py": "x", "en": "blank word"},
        {"id": 5, "cn": None, "py": "y", "en": "no word"},
    ])

    rows, merged = importer.load_rows(str(path))

    assert len(rows) == 1
    assert merged == 2
    assert rows[0]["pinyin"] == "cháng; zhǎng"
    assert rows[0]["meaning_en"] == "long; grow"


def test_merge_texts_respects_the_pinyin_column_limit():
    assert importer._merge_texts(["a", None, "b", "a"]) == "a; b"
    assert importer._merge_texts([None, ""]) is None
    # Whole senses are dropped rather than cut in half.
    assert importer._merge_texts(["abcdef", "ghijkl"], limit=10) == "abcdef"


def test_resolve_file_accepts_a_folder(tmp_path):
    workbook = tmp_path / importer.DEFAULT_NAME
    write_sheet(workbook, [{"id": 1, "cn": "书", "py": "shū", "en": "book"}])

    assert importer.resolve_file(str(tmp_path)) == str(workbook)
    assert importer.resolve_file(str(workbook)) == str(workbook)

    other = tmp_path / "another.xlsx"
    write_sheet(other, [{"id": 2, "cn": "人", "py": "rén", "en": "person"}])
    # The expected name still wins when the folder holds several workbooks.
    assert importer.resolve_file(str(tmp_path)) == str(workbook)

    workbook.unlink()
    with pytest.raises(FileNotFoundError):
        importer.resolve_file(str(tmp_path / "missing"))
    assert importer.resolve_file(str(tmp_path)) == str(other)
