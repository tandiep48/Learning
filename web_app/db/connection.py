"""
db/connection.py
-----------------
psycopg2 connection factory + database config (loaded from .env).
Every other db.* module operates on the connection this returns.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# --- DATABASE CONFIG (loaded from .env) ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'chinese')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASSWORD', 'admin')

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")
        print("Progress will not be saved.")
        return None
