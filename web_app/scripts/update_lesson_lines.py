#!/usr/bin/env python3
"""
One-off migration: normalise lesson_lines to the new HSK file naming.

For every passage, the lines are renumbered so that line_id runs 1..N (ordered by the
current line_id) and audio_key is rebuilt as '{passage_id}_{line_id}'. This matches the
new lesson JSON files exactly — verified against them, so no JSON is needed on the server.

Safety:
  * Rows are updated by primary key (id), and per passage the new line_id is always <=
    the old one and applied in ascending order, so no (passage_id, line_id) clashes occur
    mid-run.
  * Everything runs in a single transaction; the tool re-checks that (passage_id, line_id)
    is unique before committing and rolls back otherwise.
  * Run --dry-run first. Add the UNIQUE(passage_id, line_id) index AFTER a successful run
    (see schema_sql_file/schema.sql: idx_lesson_lines_passage_line).

Usage (from web_app, using the app's venv):
    python scripts/update_lesson_lines.py --dry-run
    python scripts/update_lesson_lines.py --apply

Reads the same DB_* variables as the app from web_app/.env.
"""
import os
import sys
import argparse
from collections import defaultdict

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


def compute_updates(cur):
    """Return (total_rows, [(id, new_line_id, new_audio_key), ...]) for rows that change."""
    cur.execute("""
        SELECT id, passage_id, line_id, audio_key
        FROM lesson_lines
        ORDER BY passage_id, line_id
    """)
    rows = cur.fetchall()

    by_passage = defaultdict(list)
    for row_id, passage_id, line_id, audio_key in rows:
        by_passage[passage_id].append((row_id, line_id, audio_key))

    updates = []
    for passage_id, lines in by_passage.items():
        # lines already ordered by current line_id (query ORDER BY)
        for new_line_id, (row_id, old_line_id, old_audio_key) in enumerate(lines, start=1):
            new_audio_key = f"{passage_id}_{new_line_id}"
            if old_line_id != new_line_id or old_audio_key != new_audio_key:
                updates.append((row_id, new_line_id, new_audio_key))
    return len(rows), updates


def count_duplicate_keys(cur):
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT passage_id, line_id
            FROM lesson_lines
            GROUP BY passage_id, line_id
            HAVING COUNT(*) > 1
        ) d
    """)
    return cur.fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description="Renumber lesson_lines line_id/audio_key.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    group.add_argument("--apply", action="store_true", help="apply changes in one transaction")
    args = parser.parse_args()

    conn = connect()
    try:
        with conn.cursor() as cur:
            total, updates = compute_updates(cur)

        print(f"lesson_lines rows : {total}")
        print(f"rows to change    : {len(updates)}")
        for row_id, new_line_id, new_audio_key in updates[:10]:
            print(f"    id={row_id} -> line_id={new_line_id}, audio_key={new_audio_key}")
        if len(updates) > 10:
            print(f"    ... and {len(updates) - 10} more")

        if args.dry_run:
            print("dry-run: nothing was written.")
            return

        if not updates:
            print("Nothing to update.")
            return

        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE lesson_lines SET line_id = %s, audio_key = %s WHERE id = %s",
                [(new_line_id, new_audio_key, row_id)
                 for (row_id, new_line_id, new_audio_key) in updates],
            )
            dupes = count_duplicate_keys(cur)
            if dupes:
                conn.rollback()
                print(f"ABORTED: {dupes} duplicate (passage_id, line_id) after update. Rolled back.")
                sys.exit(1)

        conn.commit()
        print(f"Applied {len(updates)} updates. (passage_id, line_id) is unique.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
