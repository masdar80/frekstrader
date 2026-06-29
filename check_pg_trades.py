import os
import psycopg2

def check_pg():
    # Since PG is running inside docker and exposes 5432, we can connect from localhost
    try:
        conn = psycopg2.connect(
            dbname="foreksdb",
            user="foreks",
            password="foreks_secret",
            host="localhost",
            port=5432
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trades")
        print(f"Total trades in PostgreSQL: {cur.fetchone()[0]}")
        cur.execute("SELECT symbol, direction, opened_at, closed_at, profit, status FROM trades ORDER BY opened_at DESC LIMIT 20")
        rows = cur.fetchall()
        print("Last 20 trades in PostgreSQL:")
        for r in rows:
            print(f"  {r[0]} {r[1]} | Opened: {r[2]} | Closed: {r[3]} | P&L: {r[4]} | Status: {r[5]}")
        conn.close()
    except Exception as e:
        print(f"Failed to check PG: {e}")

if __name__ == "__main__":
    check_pg()
