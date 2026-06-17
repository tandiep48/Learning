import psycopg2
import os
from dotenv import load_dotenv

# Load database credentials from the .env file (either in web_app/ or root directory)
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(script_dir), 'web_app', '.env'))
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'chinese')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASSWORD', 'admin')

try:
    # 1. Connect to the database
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    conn.autocommit = True
    
    # 2. Read the schema file
    schema_path = 'schema.sql' # Ensure schema.sql is in the same folder
    with open(schema_path, 'r', encoding='utf-8') as file:
        schema_query = file.read()
        
    # 3. Execute the schema script
    with conn.cursor() as cur:
        cur.execute(schema_query)
        
    print("✅ Schema updated successfully!")
    conn.close()
except Exception as e:
    print(f"❌ Error updating database: {e}")