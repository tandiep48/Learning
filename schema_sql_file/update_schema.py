import psycopg2
import os
# Update these with your Linux server's database credentials
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'chinese'
DB_USER = 'postgres'
DB_PASS = 'admin' # Make sure this matches your server password
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