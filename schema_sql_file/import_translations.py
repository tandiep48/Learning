import os
import sys
import math
import psycopg2
import pandas as pd
from dotenv import load_dotenv

# Imports sentence translations into the `translation` table. The CSV keeps the old
# `passage_id` header; it is mapped onto the table's `translation_id` column.
#
# Usage:
#   python import_translations.py [path/to/combined_translations.csv]
# Defaults to sharing_file/combined_translations.csv when no path is given.

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV = os.path.join(BASE_DIR, "combined_translations.csv")

load_dotenv(os.path.join(BASE_DIR, 'web_app', '.env'))
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'chinese')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASSWORD', 'admin')


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def import_translations(csv_path):
    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    # Accept either the CSV's original `passage_id` header or an already-renamed one.
    id_col = 'passage_id' if 'passage_id' in df.columns else 'translation_id'

    records = []
    for _, row in df.iterrows():
        translation_id = _clean(row.get(id_col))
        if not translation_id:
            continue
        records.append((
            translation_id,
            _clean(row.get('cn')),
            _clean(row.get('vn')),
            _clean(row.get('en')),
        ))

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.executemany(
            """
            INSERT INTO translation (translation_id, cn, vn, en)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (translation_id) DO UPDATE
                SET cn = EXCLUDED.cn, vn = EXCLUDED.vn, en = EXCLUDED.en
            """,
            records,
        )
        conn.commit()
        print(f"Imported {len(records)} translations from {csv_path}")
    except Exception as e:
        conn.rollback()
        print(f"Error during translation import: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    import_translations(path)
