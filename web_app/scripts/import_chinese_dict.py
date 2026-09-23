#!/usr/bin/env python3
"""
Bulk-upsert the word dictionary (chinese_dict_new.xlsx) into the database.

Target tables, all keyed off the Chinese word `cn`:

  vocabulary           upsert by cn (unique). hsk_level is derived from the
                       `tags` column ('h4, verb' -> 'HSK4') and only overwritten
                       when the sheet actually gives one.
  chinese_stroke_info  upsert by cn.
  sematic_diffculty    upsert by word_id, resolved from vocabulary.id inside the
                       database (never from the spreadsheet's own `id` column).

Nothing is deleted, so passage_vocabulary / user_saved_word foreign keys stay
intact. The sheet lists one row per sense, so rows sharing a `cn` are merged
into a single record (see load_rows) instead of overwriting each other.

The sheet is loaded into a TEMPORARY staging table with chunked multi-row
INSERTs, then each target table is written by a handful of set-based statements
(no per-word round trip), so a ~50k-row file is a few seconds of work.

Usage (from web_app, using the app's venv):
    python scripts/import_chinese_dict.py --dry-run
    python scripts/import_chinese_dict.py --apply
    python scripts/import_chinese_dict.py --apply --file /data/chinese_dict_new.xlsx
    python scripts/import_chinese_dict.py --apply --file /data          # folder holding it
    python scripts/import_chinese_dict.py --apply --chunk-size 10000

--file takes either the workbook itself or the folder it sits in; a folder is
searched for chinese_dict_new.xlsx, else for the single .xlsx it contains.

On a Linux server use scripts/import-chinese-dict.sh, which picks the venv
interpreter up automatically.

Reads the same DB_* variables as the app from web_app/.env. Point .env at the
target (production) database before running --apply.
"""
import os
import re
import sys
import argparse

from dotenv import load_dotenv
from sqlalchemy import (
    Column, Integer, MetaData, Numeric, String, Table, Text,
    func, insert, select, update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Bootstrap: put web_app on the path and load .env BEFORE importing the entity
# layer (entity.database reads the DB_* vars at import time).
_HERE = os.path.dirname(os.path.abspath(__file__))     # web_app/scripts
_WEBAPP = os.path.dirname(_HERE)                        # web_app
load_dotenv(os.path.join(_WEBAPP, ".env"))
sys.path.insert(0, _WEBAPP)

from entity.database import SessionLocal                          # noqa: E402
from entity.vocabulary.entity import Vocabulary                   # noqa: E402
from entity.sematic_difficulty.entity import SemanticDifficulty   # noqa: E402
from entity.chinese_stroke_info.entity import ChineseStrokeInfo   # noqa: E402

# The workbook sits at the repo root (Learning/) by default.
DEFAULT_NAME = "chinese_dict_new.xlsx"
DEFAULT_FILE = os.path.normpath(os.path.join(_WEBAPP, "..", DEFAULT_NAME))
DEFAULT_CHUNK = 5000

_H_TAG = re.compile(r"^h([1-7])$", re.IGNORECASE)

VOCAB = Vocabulary.__table__
SEMATIC = SemanticDifficulty.__table__
STROKE = ChineseStrokeInfo.__table__

STROKE_COLUMNS = [
    "zh", "total_strokes_cn", "total_strokes_zh", "strokes_cn", "strokes_zh",
    "word_length", "strokes_difficult_cn", "strokes_difficult_cn_norm",
    "strokes_difficult_zh", "strokes_difficult_zh_norm",
]

# Staging table: one row per spreadsheet word, typed like the target columns so
# the set-based statements below need no casts. TEMPORARY + ON COMMIT DROP means
# it disappears with the transaction, and two runs never collide.
STAGE = Table(
    "stage_chinese_dict", MetaData(),
    Column("cn", String(100), primary_key=True),
    Column("pinyin", String(100)),
    Column("meaning_en", Text),
    Column("meaning_vn", Text),
    Column("audio_key", String(100)),
    Column("hsk_level", String(10)),
    Column("sematic_difficulty", Numeric),
    Column("sematic_tags", Text),
    Column("zh", String(255)),
    Column("total_strokes_cn", Integer),
    Column("total_strokes_zh", Integer),
    Column("strokes_cn", Text),
    Column("strokes_zh", Text),
    Column("word_length", Integer),
    Column("strokes_difficult_cn", Numeric),
    Column("strokes_difficult_cn_norm", Numeric),
    Column("strokes_difficult_zh", Numeric),
    Column("strokes_difficult_zh_norm", Numeric),
    prefixes=["TEMPORARY"],
    postgresql_on_commit="DROP",
)


# --------------------------------------------------------------------------- #
# Spreadsheet
# --------------------------------------------------------------------------- #
def _hsk_from_tags(tags):
    """Derive 'HSK<n>' from a comma tag string (e.g. 'h4, verb' -> 'HSK4'), else None."""
    if not tags:
        return None
    for part in str(tags).split(","):
        m = _H_TAG.match(part.strip())
        if m:
            return "HSK" + m.group(1)
    return None


def _as_int(value):
    """Integer columns reject a float bind parameter, so round trip through int."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def resolve_file(path):
    """Accept the workbook path or the folder holding it; return the xlsx path.

    A folder resolves to chinese_dict_new.xlsx inside it, or to the single .xlsx
    it contains when that name is absent.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(path):
        return path
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Dictionary file not found: {path}")

    default = os.path.join(path, DEFAULT_NAME)
    if os.path.isfile(default):
        return default

    found = sorted(
        os.path.join(path, n) for n in os.listdir(path)
        if n.lower().endswith(".xlsx") and not n.startswith("~$")
    )
    if len(found) == 1:
        return found[0]
    if not found:
        raise FileNotFoundError(f"No .xlsx found in folder: {path}")
    names = ", ".join(os.path.basename(f) for f in found)
    raise FileNotFoundError(
        f"{path} holds several workbooks ({names}); pass the file with --file."
    )


def _text(value):
    """Trim a cell to a clean string, or None when it is blank.

    Non-breaking spaces are common in this sheet ('zhēngduó\xa0'), so collapse
    every run of whitespace — otherwise two identical senses look different.
    """
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _merge_texts(values, limit=None):
    """Join distinct senses with '; ', in sheet order, dropping blanks."""
    merged = "; ".join(dict.fromkeys(v for v in values if v))
    if not merged:
        return None
    # pinyin lands in VARCHAR(100); keep whole senses rather than cutting mid-word.
    while limit is not None and len(merged) > limit and "; " in merged:
        merged = merged.rsplit("; ", 1)[0]
    return merged[:limit] if limit is not None else merged


def load_rows(path):
    """Read the xlsx and return (rows, merged_sense_rows).

    The sheet holds one row per sense, so a word such as 会 appears several
    times ('can, to be able to' / 'will'). Rows sharing a `cn` are merged into a
    single record: pinyin and the two meaning columns keep every distinct sense
    joined with '; ', the remaining columns take the first non-empty value, and
    hsk_level takes the lowest level the word is tagged with. Sheet columns the
    schema has no home for (id, freq, pos, corpus_count) are ignored.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        idx = {name: i for i, name in enumerate(next(it))}

        def val(r, name):
            i = idx.get(name)
            return r[i] if i is not None else None

        by_cn = {}
        senses = {}
        merged_rows = 0
        for r in it:
            cn = _text(val(r, "cn"))
            if cn is None:
                continue

            row = by_cn.get(cn)
            if row is None:
                row = by_cn[cn] = {
                    "cn": cn,
                    "audio_key": _text(val(r, "audio_key")),
                    "hsk_level": _hsk_from_tags(val(r, "tags")),
                    "sematic_difficulty": val(r, "sematic_difficulty"),
                    "sematic_tags": _text(val(r, "sematic_tags")),
                    "zh": _text(val(r, "zh")),
                    "total_strokes_cn": _as_int(val(r, "total_strokes_cn")),
                    "total_strokes_zh": _as_int(val(r, "total_strokes_zh")),
                    "strokes_cn": _text(val(r, "strokes_cn")),
                    "strokes_zh": _text(val(r, "strokes_zh")),
                    "word_length": _as_int(val(r, "word_length")),
                    "strokes_difficult_cn": val(r, "strokes_difficult_cn"),
                    "strokes_difficult_cn_norm": val(r, "strokes_difficult_cn_norm"),
                    "strokes_difficult_zh": val(r, "strokes_difficult_zh"),
                    "strokes_difficult_zh_norm": val(r, "strokes_difficult_zh_norm"),
                }
                senses[cn] = {"pinyin": [], "meaning_en": [], "meaning_vn": []}
            else:
                merged_rows += 1
                # A later row only fills the gaps the first one left.
                for key, cell in (
                    ("audio_key", _text(val(r, "audio_key"))),
                    ("sematic_difficulty", val(r, "sematic_difficulty")),
                    ("sematic_tags", _text(val(r, "sematic_tags"))),
                    ("zh", _text(val(r, "zh"))),
                    ("strokes_cn", _text(val(r, "strokes_cn"))),
                    ("strokes_zh", _text(val(r, "strokes_zh"))),
                ):
                    if row[key] is None:
                        row[key] = cell
                # A word taught at HSK1 and re-tagged h5 later stays HSK1.
                level = _hsk_from_tags(val(r, "tags"))
                if level is not None and (row["hsk_level"] is None or level < row["hsk_level"]):
                    row["hsk_level"] = level

            sense = senses[cn]
            sense["pinyin"].append(_text(val(r, "py")))
            sense["meaning_en"].append(_text(val(r, "en")))
            sense["meaning_vn"].append(_text(val(r, "vn")))

        for cn, row in by_cn.items():
            sense = senses[cn]
            row["pinyin"] = _merge_texts(sense["pinyin"], limit=100)
            row["meaning_en"] = _merge_texts(sense["meaning_en"])
            row["meaning_vn"] = _merge_texts(sense["meaning_vn"])

        return list(by_cn.values()), merged_rows
    finally:
        wb.close()


# --------------------------------------------------------------------------- #
# Staging
# --------------------------------------------------------------------------- #
def fill_stage(session, rows, chunk_size):
    """Create the temp table and load every row into it with chunked inserts."""
    STAGE.create(bind=session.connection())
    stmt = insert(STAGE)
    for start in range(0, len(rows), chunk_size):
        session.execute(stmt, rows[start:start + chunk_size])


def report(session):
    """Count what the apply would insert vs update, reading only the staged rows."""
    staged = session.scalar(select(func.count()).select_from(STAGE))

    vocab_existing = session.scalar(
        select(func.count()).select_from(STAGE.join(VOCAB, VOCAB.c.cn == STAGE.c.cn))
    )
    stroke_existing = session.scalar(
        select(func.count()).select_from(STAGE.join(STROKE, STROKE.c.cn == STAGE.c.cn))
    )
    # count(DISTINCT) because the live sematic_diffculty can hold several rows
    # per word_id (see upsert_sematic_difficulty).
    sematic_existing = session.scalar(
        select(func.count(func.distinct(VOCAB.c.id))).select_from(
            STAGE.join(VOCAB, VOCAB.c.cn == STAGE.c.cn)
                 .join(SEMATIC, SEMATIC.c.word_id == VOCAB.c.id)
        )
    )
    return {
        "words": staged,
        "vocab_new": staged - vocab_existing,
        "vocab_update": vocab_existing,
        "stroke_new": staged - stroke_existing,
        "stroke_update": stroke_existing,
        "sematic_update": sematic_existing,
    }


# --------------------------------------------------------------------------- #
# Upserts
# --------------------------------------------------------------------------- #
def upsert_vocabulary(session):
    """INSERT ... SELECT from the staging table, ON CONFLICT (cn) DO UPDATE."""
    source = select(
        STAGE.c.cn, STAGE.c.pinyin, STAGE.c.meaning_en, STAGE.c.meaning_vn,
        STAGE.c.audio_key, STAGE.c.hsk_level,
    )
    stmt = pg_insert(VOCAB).from_select(
        ["cn", "pinyin", "meaning_en", "meaning_vn", "audio_key", "hsk_level"], source
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[VOCAB.c.cn],
        set_={
            "pinyin": stmt.excluded.pinyin,
            "meaning_en": stmt.excluded.meaning_en,
            "meaning_vn": stmt.excluded.meaning_vn,
            "audio_key": stmt.excluded.audio_key,
            # The sheet only tags some words, so keep the stored level when it is blank.
            "hsk_level": func.coalesce(stmt.excluded.hsk_level, VOCAB.c.hsk_level),
        },
    )
    session.execute(stmt)

    # `source` is set on insert only; an existing word keeps whatever it had.
    session.execute(
        update(VOCAB)
        .where(VOCAB.c.cn == STAGE.c.cn, VOCAB.c.source.is_(None))
        .values(source="dictionary")
    )


def upsert_stroke_info(session):
    """INSERT ... SELECT from the staging table, ON CONFLICT (cn) DO UPDATE."""
    source = select(STAGE.c.cn, *[STAGE.c[c] for c in STROKE_COLUMNS])
    stmt = pg_insert(STROKE).from_select(["cn"] + STROKE_COLUMNS, source)
    stmt = stmt.on_conflict_do_update(
        index_elements=[STROKE.c.cn],
        set_={c: stmt.excluded[c] for c in STROKE_COLUMNS},
    )
    session.execute(stmt)


def upsert_sematic_difficulty(session):
    """Update the rows that exist, then insert the ones that do not.

    ON CONFLICT is not usable here: the live `sematic_diffculty` holds duplicate
    word_id rows despite the primary key in schema.sql, so there is no unique
    index for Postgres to arbitrate on. The UPDATE below simply refreshes every
    matching row.
    """
    session.execute(
        update(SEMATIC)
        .where(SEMATIC.c.word_id == VOCAB.c.id, VOCAB.c.cn == STAGE.c.cn)
        .values(
            sematic_difficulty=STAGE.c.sematic_difficulty,
            tags=STAGE.c.sematic_tags,
        )
    )

    already_there = (
        select(SEMATIC.c.word_id).where(SEMATIC.c.word_id == VOCAB.c.id).exists()
    )
    missing = (
        select(VOCAB.c.id, STAGE.c.sematic_difficulty, STAGE.c.sematic_tags)
        .select_from(STAGE.join(VOCAB, VOCAB.c.cn == STAGE.c.cn))
        .where(~already_there)
    )
    session.execute(
        insert(SEMATIC).from_select(["word_id", "sematic_difficulty", "tags"], missing)
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(
        description="Bulk-upsert the word dictionary spreadsheet into the database."
    )
    parser.add_argument("--file", default=DEFAULT_FILE,
                        help=f"dictionary xlsx, or the folder holding it "
                             f"(default: {DEFAULT_FILE})")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK,
                        help=f"rows per staging INSERT (default: {DEFAULT_CHUNK})")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    group.add_argument("--apply", action="store_true", help="write every table in one transaction")
    args = parser.parse_args()

    if args.chunk_size < 1:
        print("--chunk-size must be at least 1", file=sys.stderr)
        sys.exit(1)

    try:
        path = resolve_file(args.file)
    except (FileNotFoundError, OSError) as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    rows, merged_rows = load_rows(path)
    if not rows:
        print(f"No usable rows in {path} (every row is missing `cn`).")
        sys.exit(1)

    session = SessionLocal()
    try:
        fill_stage(session, rows, args.chunk_size)
        stats = report(session)

        print("Dictionary:")
        print(f"  file        : {path}")
        print(f"  words       : {stats['words']}  (merged {merged_rows} extra sense rows)")
        print(f"  vocabulary  : new {stats['vocab_new']}, update {stats['vocab_update']}")
        print(f"  stroke_info : new {stats['stroke_new']}, update {stats['stroke_update']}")
        print(f"  sematic     : update {stats['sematic_update']}, "
              f"new {stats['words'] - stats['sematic_update']}")
        print()

        if args.dry_run:
            session.rollback()
            print("dry-run: nothing was written.")
            return

        upsert_vocabulary(session)
        upsert_stroke_info(session)
        upsert_sematic_difficulty(session)

        session.commit()
        print("Applied: every table committed in one transaction.")
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


if __name__ == "__main__":
    main()
