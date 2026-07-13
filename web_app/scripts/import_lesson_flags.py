#!/usr/bin/env python3
"""
One-off migration: add lesson_lines.flag and populate it from the *_flag.json files.

flag = 1 means the line introduces a new word; the lesson trainer only quizzes
flagged lines (flag = 0 lines are review-only and skipped). Each JSON file holds a
list of passages, each with per-line "flag" values, e.g. H1_flag.json ... H6_flag.json.

The tool only UPDATES the flag on lines that already exist in lesson_lines; lines in
the JSON that are not in the DB are reported, never inserted.

Usage (from web_app, using the app's venv):
    python scripts/import_lesson_flags.py --dir /path/to/json --dry-run
    python scripts/import_lesson_flags.py --dir /path/to/json --apply

Reads the same DB_* variables as the app from web_app/.env.
"""
import os
import sys
import glob
import json
import argparse

import psycopg2
from dotenv import load_dotenv


def connect():
    here = os.path.dirname(os.path.abspath(__file__))          # web_app/scripts
    webapp = os.path.dirname(here)                             # web_app
    load_dotenv(os.path.join(webapp, ".env"))
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def load_flags(json_dir, pattern):
    """Read every matching JSON file and return (files, {(passage_id, line_id): flag}, total_lines)."""
    files = sorted(glob.glob(os.path.join(json_dir, pattern)))
    if not files:
        print(f"No files matching '{pattern}' in {json_dir}")
        sys.exit(1)

    flags = {}
    total_lines = 0
    for path in files:
        # utf-8-sig tolerates a BOM (PowerShell-exported JSON often has one).
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        for passage in data:
            passage_id = passage.get("passage_id")
            if not passage_id:
                continue
            for line in passage.get("lines", []):
                line_id = line.get("line_id")
                if line_id is None:
                    continue
                flags[(passage_id, int(line_id))] = 1 if int(line.get("flag", 1)) else 0
                total_lines += 1
    return files, flags, total_lines


def main():
    parser = argparse.ArgumentParser(description="Populate lesson_lines.flag from *_flag.json files.")
    parser.add_argument("--dir", default=".", help="directory holding the *_flag.json files (default: .)")
    parser.add_argument("--pattern", default="*_flag.json", help="glob for the JSON files (default: *_flag.json)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    group.add_argument("--apply", action="store_true", help="add the column if needed and apply flags in one transaction")
    args = parser.parse_args()

    files, flags, total_lines = load_flags(args.dir, args.pattern)

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT passage_id, line_id FROM lesson_lines")
            existing = {(p, l) for p, l in cur.fetchall()}

        present = {k: v for k, v in flags.items() if k in existing}
        missing = [k for k in flags if k not in existing]
        zero = sum(1 for v in present.values() if v == 0)

        print(f"files                 : {len(files)}")
        print(f"lines in JSON         : {total_lines} ({len(flags)} unique passage/line)")
        print(f"matched in DB         : {len(present)}  (flag=1: {len(present) - zero}, flag=0: {zero})")
        print(f"not found in DB       : {len(missing)}")
        for passage_id, line_id in missing[:10]:
            print(f"    missing: passage_id={passage_id} line_id={line_id}")
        if len(missing) > 10:
            print(f"    ... and {len(missing) - 10} more")

        if args.dry_run:
            print("dry-run: nothing was written.")
            return

        if not present:
            print("Nothing to update.")
            return

        with conn.cursor() as cur:
            cur.execute("ALTER TABLE lesson_lines ADD COLUMN IF NOT EXISTS flag SMALLINT DEFAULT 1")
            cur.executemany(
                "UPDATE lesson_lines SET flag = %s WHERE passage_id = %s AND line_id = %s",
                [(v, passage_id, line_id) for (passage_id, line_id), v in present.items()],
            )
        conn.commit()
        print(f"Applied flag on {len(present)} lines.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
