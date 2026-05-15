import psycopg2
import os

def rename_tables():
    conn = psycopg2.connect(host="localhost", database="chinese", user="postgres", password="admin")
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
