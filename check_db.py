
import sqlite3
conn = sqlite3.connect('foreks.db')
cur = conn.cursor()
cur.execute("SELECT id, symbol, external_id, volume, opened_at FROM trades WHERE status = 'closed' AND profit = 0.0")
rows = cur.fetchall()
print(f"Found {len(rows)} closed trades with 0 profit:")
for r in rows:
    print(r)
conn.close()
