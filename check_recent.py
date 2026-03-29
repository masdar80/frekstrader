import sqlite3
import datetime

def check_recent_data():
    conn = sqlite3.connect('foreks.db')
    cur = conn.cursor()
    
    # Get tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]
    print(f"Tables: {tables}")
    
    if 'trades' in tables:
        print("\nLast 20 trades:")
        cur.execute("SELECT id, symbol, volume, opened_at, closed_at, status, profit FROM trades ORDER BY opened_at DESC LIMIT 20")
        for row in cur.fetchall():
            print(row)
            
    if 'history' in tables:
        print("\nLast 20 history entries:")
        cur.execute("SELECT id, time, type, symbol, volume FROM history ORDER BY time DESC LIMIT 20")
        for row in cur.fetchall():
            print(row)
            
    conn.close()

if __name__ == "__main__":
    check_recent_data()
