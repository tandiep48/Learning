import psycopg2
import json
import pandas as pd
import os
import sys
import math

def clean_nan(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "web_app", "data")
VOCAB_DIR = os.path.join(DATA_DIR, "vocab_data")
LESSON_DIR = os.path.join(DATA_DIR, "lesson_practice")
SHARING_DIR = os.path.join(BASE_DIR, "sharing_file")

def import_data():
    conn = psycopg2.connect(host="localhost", database="chinese", user="postgres", password="admin")
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Clear existing data
        cur.execute("TRUNCATE vocabulary, lesson_passages, passage_vocabulary RESTART IDENTITY;")
        print("Cleared existing content tables.")

        # 1. Import final_chinese_dict.json (Dictionary)
        dict_path = os.path.join(VOCAB_DIR, "final_chinese_dict.json")
        if os.path.exists(dict_path):
            with open(dict_path, 'r', encoding='utf-8') as f:
                dict_data = json.load(f)
            
            vocab_records = []
            for item in dict_data:
                cn = item.get('cn', '')
                pinyin = item.get('pinyin', '')
                audio_key = item.get('audio_key', '')
                
                # Extract first definition for meaning
                meaning_en = ""
                meaning_vn = ""
                hsk_level = None
                
                defs = item.get('definitions', [])
                if defs:
                    meaning_en = defs[0].get('meaning_en', '')
                    meaning_vn = defs[0].get('meaning_vn', '')
                    
                    tags = defs[0].get('tags', [])
                    for t in tags:
                        if t.startswith('H') and len(t) <= 2:
                            hsk_level = "HSK" + t[1:]
                            break
                            
                vocab_records.append((cn, pinyin, meaning_en, meaning_vn, audio_key, hsk_level, 'dictionary'))
                
            cur.executemany(
                "INSERT INTO vocabulary (cn, pinyin, meaning_en, meaning_vn, audio_key, hsk_level, source) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                vocab_records
            )
            print(f"Imported {len(vocab_records)} words from final_chinese_dict.json")

        # 2. Import chinese_vocabulary.xlsx (Course Vocab)
        course_vocab_path = os.path.join(VOCAB_DIR, "chinese_vocabulary.xlsx")
        if os.path.exists(course_vocab_path):
            df = pd.read_excel(course_vocab_path)
            # Schema: word, pinyin, level, meaning_vn, meaning_en
            course_records = []
            for _, row in df.iterrows():
                if pd.isna(row.get('word')):
                    continue
                cn = str(row['word'])
                pinyin = str(row['pinyin']) if not pd.isna(row.get('pinyin')) else ''
                meaning_en = str(row['meaning_en']) if not pd.isna(row.get('meaning_en')) else ''
                meaning_vn = str(row['meaning_vn']) if not pd.isna(row.get('meaning_vn')) else ''
                level = str(row['level']) if not pd.isna(row.get('level')) else None
                
                # We need audio_key. We can fetch it from the dictionary data if we want, or leave it blank and join later.
                # Since dict data is already populated, we'll just insert it as 'course'.
                # Actually, the user wants the course vocab to just be a source. 
                # Let's see if we should lookup audio key from dict_data.
                audio_key = ""
                if os.path.exists(dict_path):
                    for d in dict_data:
                        if d['cn'] == cn:
                            audio_key = d['audio_key']
                            break

                course_records.append((cn, pinyin, meaning_en, meaning_vn, audio_key, level, 'course'))

            cur.executemany(
                "INSERT INTO vocabulary (cn, pinyin, meaning_en, meaning_vn, audio_key, hsk_level, source) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                course_records
            )
            print(f"Imported {len(course_records)} words from chinese_vocabulary.xlsx")

        # 3. Import Lesson Passages (JSONs)
        passage_files = [f for f in os.listdir(LESSON_DIR) if f.startswith('HSK') and f.endswith('.json')]
        passage_count = 0
        for p_file in passage_files:
            hsk_level = p_file.split('_')[0]
            with open(os.path.join(LESSON_DIR, p_file), 'r', encoding='utf-8') as f:
                passages = json.load(f)
                
            for p in passages:
                passage_id = p.get('passage_id')
                if passage_id:
                    # Clean NaNs before converting to JSON string for Postgres
                    clean_p = clean_nan(p)
                    # Store the whole object as jsonb
                    cur.execute(
                        "INSERT INTO lesson_passages (passage_id, hsk_level, content) VALUES (%s, %s, %s) ON CONFLICT (passage_id) DO NOTHING",
                        (passage_id, hsk_level, json.dumps(clean_p, ensure_ascii=False))
                    )
                    passage_count += 1
        print(f"Imported {passage_count} lesson passages.")

        # 4. Import Passage Vocabulary Mapping
        mapping_path = os.path.join(SHARING_DIR, "vocab_lesson_info (1).xlsx")
        if os.path.exists(mapping_path):
            df_map = pd.read_excel(mapping_path)
            # Schema: ['Course', 'Lesson', 'Part', 'NoID', 'cn', 'word_id', 'pinyin', 'meaning_vn', 'meaning_en', 'passage_id']
            map_records = []
            for _, row in df_map.iterrows():
                passage_id = str(row.get('passage_id'))
                cn = str(row.get('cn'))
                if pd.notna(passage_id) and pd.notna(cn) and passage_id != 'nan' and cn != 'nan':
                    map_records.append((passage_id, cn))
            
            # Use ON CONFLICT DO NOTHING to ignore duplicates
            cur.executemany(
                "INSERT INTO passage_vocabulary (passage_id, cn) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                map_records
            )
            print(f"Imported {len(map_records)} passage-vocabulary mappings.")

        conn.commit()
        print("Data migration successful!")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import_data()
