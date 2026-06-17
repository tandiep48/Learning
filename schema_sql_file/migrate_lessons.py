import psycopg2
import json
import os
from dotenv import load_dotenv

# Load database credentials from .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(script_dir), 'web_app', '.env'))
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'chinese')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASSWORD', 'admin')

def migrate():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Create table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lesson_lines (
                id SERIAL PRIMARY KEY,
                passage_id VARCHAR(100) REFERENCES lesson_passages(passage_id) ON DELETE CASCADE,
                line_id INT,
                speaker VARCHAR(50),
                content TEXT,
                pinyin TEXT,
                audio_key VARCHAR(100),
                translation_en TEXT,
                translation_vi TEXT,
                tokens JSONB
            );
            
            -- Clear just in case
            TRUNCATE lesson_lines RESTART IDENTITY;
        """)

        # 2. Fetch all passages
        cur.execute("SELECT passage_id, content FROM lesson_passages WHERE content IS NOT NULL")
        passages = cur.fetchall()

        insert_records = []
        for p_id, content in passages:
            # content is already a dict in psycopg2 for JSONB
            lines = content.get('lines', [])
            for line in lines:
                translations = line.get('translations', {})
                insert_records.append((
                    p_id,
                    line.get('line_id'),
                    line.get('speaker'),
                    line.get('content'),
                    line.get('pinyin'),
                    line.get('audio_key'),
                    translations.get('en'),
                    translations.get('vi'),
                    json.dumps(line.get('tokens', []), ensure_ascii=False)
                ))

        # 3. Insert records
        cur.executemany("""
            INSERT INTO lesson_lines (
                passage_id, line_id, speaker, content, pinyin, audio_key, translation_en, translation_vi, tokens
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, insert_records)
        
        print(f"Migrated {len(insert_records)} lesson lines!")
        
        # 4. Drop content column from lesson_passages
        cur.execute("ALTER TABLE lesson_passages DROP COLUMN content;")
        
        conn.commit()
        print("Dropped JSONB content column.")
        
    except Exception as e:
        conn.rollback()
        print("Error during migration:", e)
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    migrate()
