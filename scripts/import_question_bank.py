"""
import_question_bank.py
Imports practice and exam JSON files from sharing_file/learning_units/ into question_bank.
Run: python scripts/import_question_bank.py
"""
import os
import json
import ast

import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG   = dict(host='localhost', dbname='chinese', user='postgres', password='admin')
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNITS_DIR   = os.path.join(BASE_DIR, 'sharing_file', 'learning_units')

SOURCES = [
    ('practice', 'practice-{}.json', range(1, 7)),
    ('exam',     'exam-{}.json',     range(1, 7)),
]

INSERT_SQL = """
    INSERT INTO question_bank
        (level, category, lesson, no, skill, type, content, question,
         answer, audio_key, image, options, progress, unit_id)
    VALUES %s
    ON CONFLICT (category, level, lesson, no) DO UPDATE SET
        skill     = EXCLUDED.skill,
        type      = EXCLUDED.type,
        content   = EXCLUDED.content,
        question  = EXCLUDED.question,
        answer    = EXCLUDED.answer,
        audio_key = EXCLUDED.audio_key,
        image     = EXCLUDED.image,
        options   = EXCLUDED.options,
        progress  = EXCLUDED.progress,
        unit_id   = EXCLUDED.unit_id
"""


def normalise_options(raw):
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            result = ast.literal_eval(raw)
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return None


def normalise_audio_key(raw):
    if raw is None:
        return None
    if isinstance(raw, list):
        return json.dumps(raw, ensure_ascii=False)
    return str(raw)


def normalise_image(raw):
    """image can be a string, list, or None — store as string."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return json.dumps(raw, ensure_ascii=False)
    return str(raw)


def load_rows(category, filepath, level):
    if not os.path.exists(filepath):
        print(f'  ⚠️  Not found: {filepath}')
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rows = []
    for item in data:
        opts = normalise_options(item.get('options'))
        rows.append((
            int(item.get('level', level)),
            category,
            int(item.get('lesson', 0)),          # lesson is integer in new files
            item.get('no'),
            item.get('skill', 'listening'),
            item.get('type'),
            item.get('content'),
            item.get('question'),
            str(item.get('answer')) if item.get('answer') is not None else None,
            normalise_audio_key(item.get('audio_key')),
            normalise_image(item.get('image')),
            json.dumps(opts, ensure_ascii=False) if opts is not None else None,
            str(item.get('progress', '')),
            str(item.get('unit_id', '')),
        ))
    return rows


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    total = 0
    try:
        for category, template, levels in SOURCES:
            for lvl in levels:
                path = os.path.join(UNITS_DIR, template.format(lvl))
                rows = load_rows(category, path, lvl)
                if not rows:
                    continue
                with conn.cursor() as cur:
                    execute_values(cur, INSERT_SQL, rows)
                conn.commit()
                print(f'  [OK]  {category}-{lvl}: {len(rows)} rows')
                total += len(rows)

        print(f'\n[DONE] Total upserted: {total}')
        with conn.cursor() as cur:
            cur.execute("SELECT category, COUNT(*) FROM question_bank GROUP BY category ORDER BY category")
            for r in cur.fetchall():
                print(f'   {r[0]}: {r[1]} rows')
    except Exception as e:
        conn.rollback()
        print(f'\n[ERROR] {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
