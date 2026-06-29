import os
import sqlite3

def reset_db():
    db_path = 'foreks.db'
    if os.path.exists(db_path):
        print(f"Deleting existing database: {db_path}")
        try:
            os.remove(db_path)
            print("Database deleted successfully!")
        except Exception as e:
            print(f"Error deleting database: {e}")
            print("Trying to truncate tables instead...")
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("DELETE FROM trades")
                cur.execute("DELETE FROM decisions")
                cur.execute("DELETE FROM signals")
                cur.execute("DELETE FROM account_snapshots")
                conn.commit()
                conn.close()
                print("All tables truncated successfully!")
            except Exception as ex:
                print(f"Failed to truncate tables: {ex}")
    else:
        print("No database file found to delete.")

if __name__ == "__main__":
    reset_db()
