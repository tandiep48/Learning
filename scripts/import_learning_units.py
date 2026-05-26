"""
import_learning_units.py
Imports sharing_file/learning_units/learning_units.csv into the learning_units table.
Run: python scripts/import_learning_units.py
"""
import os
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd

DB_CONFIG = dict(host='localhost', dbname='chinese', user='postgres', password='admin')
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH  = os.path.join(BASE_DIR, 'sharing_file', 'learning_units', 'learning_units.csv')

INSERT_SQL = """
    INSERT INTO learning_units (unit_id, unique_word) VALUES %s
"""


def main():
    print(f'Reading {CSV_PATH} ...')
    df = pd.read_csv(CSV_PATH, usecols=['unit_id', 'unique_word'])
    df = df.dropna(subset=['unit_id', 'unique_word'])
    df['unit_id']     = df['unit_id'].astype(str).str.strip()
    df['unique_word'] = df['unique_word'].astype(str).str.strip()

    rows = list(df[['unit_id', 'unique_word']].itertuples(index=False, name=None))
    print(f'Total rows to insert: {len(rows)}')

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # Clear old data then bulk insert
            cur.execute('TRUNCATE learning_units RESTART IDENTITY')
            execute_values(cur, INSERT_SQL, rows, page_size=5000)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM learning_units')
            count = cur.fetchone()[0]
        print(f'[DONE] learning_units now has {count:,} rows.')

        # Sample verification
        with conn.cursor() as cur:
            cur.execute("SELECT unit_id, COUNT(*) as words FROM learning_units GROUP BY unit_id ORDER BY unit_id LIMIT 5")
            print('\nSample unit word counts:')
            for r in cur.fetchall():
                print(f'   {r[0]}: {r[1]} words')

    except Exception as e:
        conn.rollback()
        print(f'\n[ERROR] {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
