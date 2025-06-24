import os
import Campus_Hub.models as models
from Campus_Hub.config import DB_PATH

def reset_database():
    print("Resetting database...")
    
    # Remove existing database file if it exists
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"Removed existing database at {DB_PATH}")
        except Exception as e:
            print(f"Error removing database: {e}")
            return False
    
    # Initialize the database from scratch
    try:
        models.init_db()
        print("Database initialized successfully!")
        
        # Verify tables were created
        conn = models.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cur.fetchall()]
        print(f"Created tables: {tables}")
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

if __name__ == "__main__":
    success = reset_database()
    if success:
        print("\nDatabase reset complete. You can now run Main.py to start the application.")
    else:
        print("\nDatabase reset failed. Please check the error messages above.")