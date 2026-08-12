#!/usr/bin/env python3
"""
Import the cover-book lessons into lesson_passages + lesson_lines.

The 15 topic "books" (AML, CHE, ...) reuse the existing lesson tables. Each book has a
JSON file (a list of passages) in content_info/Final/{CODE}.json with passage_id of the
form {CODE}_{lesson}_{part} and lines carrying content/pinyin/audio_key/translations/tokens.
Book passages are tagged with book_code and left with hsk_level = NULL so they stay out of
the HSK queries; regular HSK passages are never touched.

Re-runnable: a passage's lines are fully replaced on each apply (delete + insert), so
importing the same book twice yields the same result.

Usage (from web_app, using the app's venv):
    python scripts/import_book_lessons.py --dry-run
    python scripts/import_book_lessons.py --apply
    python scripts/import_book_lessons.py --apply --codes AML,CHE
    python scripts/import_book_lessons.py --apply --source /path/to/Final

Reads the same DB_* variables as the app from web_app/.env.
"""
import os
import sys
import json
import argparse

from dotenv import load_dotenv

# Bootstrap: put web_app on the path and load .env BEFORE importing the entity layer
# (entity.database reads the DB_* vars at import time).
_HERE = os.path.dirname(os.path.abspath(__file__))     # web_app/scripts
_WEBAPP = os.path.dirname(_HERE)                        # web_app
load_dotenv(os.path.join(_WEBAPP, ".env"))
sys.path.insert(0, _WEBAPP)

from entity.database import SessionLocal                # noqa: E402
from entity.passage.entity import LessonPassage         # noqa: E402
from entity.lesson_line.entity import LessonLine        # noqa: E402

# The 15 books that have a matching cover image; only these are imported.
BOOK_CODES = [
    "AML", "CHE", "DSBD", "IBT", "IE", "KB", "LM", "LOG",
    "OFC", "OW", "SA", "SC", "SD", "SR", "TOU",
]

# content_info/Final sits next to the Learning repo (YiChinese/content_info/Final).
DEFAULT_SOURCE = os.path.normpath(
    os.path.join(_WEBAPP, "..", "..", "content_info", "Final")
)


def load_book(source_dir, code):
    """Load one book JSON and return its list of passage dicts."""
    path = os.path.join(source_dir, f"{code}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    # utf-8-sig tolerates a BOM (PowerShell-exported JSON often has one).
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of passages, got {type(data).__name__}")
    return data


def replace_passage(session, code, passage):
    """Upsert one passage and fully replace its lines. Returns (is_new, line_count)."""
    passage_id = passage["passage_id"]

    row = session.get(LessonPassage, passage_id)
    is_new = row is None
    if is_new:
        session.add(LessonPassage(passage_id=passage_id, hsk_level=None, book_code=code))
    else:
        row.book_code = code
        row.hsk_level = None

    # Replace lines: DELETE runs immediately, so the inserts below never clash on the
    # (passage_id, line_id) unique index.
    session.query(LessonLine).filter(LessonLine.passage_id == passage_id).delete(
        synchronize_session=False
    )

    lines = passage.get("lines", []) or []
    for line in lines:
        translations = line.get("translations") or {}
        session.add(LessonLine(
            passage_id=passage_id,
            line_id=line.get("line_id"),
            speaker=line.get("speaker"),
            content=line.get("content"),
            pinyin=line.get("pinyin"),
            audio_key=line.get("audio_key"),
            translation_en=translations.get("en"),
            translation_vi=translations.get("vi"),
            tokens=line.get("tokens") or [],
        ))
    return is_new, len(lines)


def main():
    parser = argparse.ArgumentParser(description="Import cover-book lessons into lesson_passages/lesson_lines.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help=f"folder holding {{CODE}}.json (default: {DEFAULT_SOURCE})")
    parser.add_argument("--codes", default="", help="comma-separated subset of book codes (default: all 15)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    group.add_argument("--apply", action="store_true", help="import in one transaction")
    args = parser.parse_args()

    if args.codes:
        codes = [c.strip().upper() for c in args.codes.split(",") if c.strip()]
        unknown = [c for c in codes if c not in BOOK_CODES]
        if unknown:
            print(f"Unknown codes (not in the cover-book list): {', '.join(unknown)}")
            sys.exit(1)
    else:
        codes = list(BOOK_CODES)

    print(f"source : {args.source}")
    print(f"books  : {len(codes)} ({', '.join(codes)})")
    print()

    session = SessionLocal()
    try:
        # Which book passages already exist, so the report can show new vs replaced.
        existing_pids = {
            pid for (pid,) in session.query(LessonPassage.passage_id)
            .filter(LessonPassage.book_code.isnot(None)).all()
        }

        grand_passages = grand_lines = grand_new = 0
        for code in codes:
            data = load_book(args.source, code)
            bad = [p.get("passage_id") for p in data
                   if not str(p.get("passage_id", "")).startswith(f"{code}_")]
            new_count = sum(1 for p in data if p["passage_id"] not in existing_pids)
            line_count = sum(len(p.get("lines", []) or []) for p in data)

            print(f"  {code:5} passages={len(data):4}  lines={line_count:5}  "
                  f"new={new_count:4}  replace={len(data) - new_count:4}"
                  + (f"  BAD_ID={bad[:3]}" if bad else ""))

            grand_passages += len(data)
            grand_lines += line_count
            grand_new += new_count

            if args.apply:
                for passage in data:
                    replace_passage(session, code, passage)

        print()
        print(f"TOTAL  passages={grand_passages}  lines={grand_lines}  "
              f"new={grand_new}  replace={grand_passages - grand_new}")

        if args.dry_run:
            print("dry-run: nothing was written.")
            return

        session.commit()
        print("Applied: book lessons imported.")
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


if __name__ == "__main__":
    main()
