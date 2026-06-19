import sys
import psycopg2
from werkzeug.security import generate_password_hash
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

def update_user_password(target_username, new_password):
    # Generate the hash just like your register route does
    hashed_password = generate_password_hash(new_password)
    
    try:
        # Connect to your database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cursor = conn.cursor()
        
        # Execute the UPDATE statement
        update_query = "UPDATE users SET password = %s WHERE username = %s"
        cursor.execute(update_query, (hashed_password, target_username))
        
        # Check if the user was actually found and updated
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✅ Successfully updated password for user: '{target_username}'")
        else:
            print(f"❌ User '{target_username}' not found in the database.")
            
    except Exception as e:
        print(f"⚠️ An error occurred: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Check if the user provided the correct number of arguments
    if len(sys.argv) != 3:
        print("Usage: python change_password.py <username> <new_password>")
        sys.exit(1)
        
    username_arg = sys.argv[1]
    new_password_arg = sys.argv[2]
    
    update_user_password(username_arg, new_password_arg)
