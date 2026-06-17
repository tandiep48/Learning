import psycopg2
import os
from dotenv import load_dotenv

def rename_tables():
    # Load database credentials from .env file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(os.path.dirname(script_dir), 'web_app', '.env'))
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
    conn.autocommit = True
    cur = conn.cursor()
    
    script_path = r"d:\MyProject\Python\Learning\schema_sql_file\rename_update_at.sql"
    with open(script_path, "r") as f:
        sql = f.read()
        
    try:
        cur.execute(sql)
        print("Tables renamed successfully.")
    except Exception as e:
        print(f"Error executing SQL: {e}")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    rename_tables()
