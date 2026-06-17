import os
import glob
import pandas as pd
import psycopg2
import math

def clean_nan(val):
    if pd.isna(val):
        return None
    return str(val)

def import_grammar():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sharing_dir = os.path.join(base_dir, "sharing_file")
    
    excel_files = glob.glob(os.path.join(sharing_dir, "Grammar_*.xlsx"))
    
    if not excel_files:
        print("No Grammar Excel files found in sharing_file/")
        return
    from dotenv import load_dotenv

    # Load database credentials from .env file
    load_dotenv(os.path.join(base_dir, 'web_app', '.env'))
    load_dotenv()

    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'chinese')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASS = os.getenv('DB_PASSWORD', 'admin')

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("TRUNCATE grammar_rule, grammar_context RESTART IDENTITY;")
        print("Cleared existing grammar_rule and grammar_context data.")

        records = []
        context_records = []
        
        for file in excel_files:
            try:
                # Read all sheets
                xls = pd.ExcelFile(file)
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    
                    if sheet_name == 'Grammar':
                        # Schema: GrammarID, Type, Passage_Number, vietnamese, english
                        for _, row in df.iterrows():
                            grammar_id = str(row.get('GrammarID', ''))
                            if grammar_id == 'nan' or not grammar_id:
                                continue
                                
                            t_val = row.get('Type')
                            g_type = int(t_val) if not pd.isna(t_val) else None
                            
                            p_val = row.get('Passage_Number')
                            passage_number = int(p_val) if not pd.isna(p_val) else None
                            
                            vietnamese = clean_nan(row.get('vietnamese'))
                            english = clean_nan(row.get('english'))
                            
                            records.append((grammar_id, g_type, passage_number, vietnamese, english))
                    else:
                        # Tab is a context table
                        # Convert DataFrame to JSON records
                        # clean nan before dumping
                        df = df.where(pd.notnull(df), None)
                        content_json = df.to_json(orient='records', force_ascii=False)
                        context_records.append((sheet_name, content_json))
                        
                print(f"Processed {os.path.basename(file)}")
            except Exception as e:
                print(f"Error reading {file}: {e}")

        if records:
            cur.executemany(
                "INSERT INTO grammar_rule (grammar_id, type, passage_number, vietnamese_content, english_content) VALUES (%s, %s, %s, %s, %s)",
                records
            )
            print(f"Imported {len(records)} grammar rules successfully.")
            
        if context_records:
            cur.executemany(
                "INSERT INTO grammar_context (grammar_id, content_json) VALUES (%s, %s)",
                context_records
            )
            print(f"Imported {len(context_records)} grammar context tables successfully.")
            
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"Database error during import: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import_grammar()
