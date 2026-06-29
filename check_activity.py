import sqlite3
db = sqlite3.connect(r'd:\foreks\foreks.db')
cur = db.cursor()

print("=== DECISIONS LAST 10 DAYS ===")
cur.execute("""SELECT DATE(timestamp) as day, action, COUNT(*) as cnt
               FROM decisions WHERE timestamp >= '2026-06-01' GROUP BY day, action ORDER BY day DESC""")
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]}: {r[2]}")

print()
cur.execute("SELECT COUNT(*) as cnt FROM signals WHERE timestamp >= '2026-06-01'")
r = cur.fetchone()
print(f"Signals in last 10 days: {r[0]}")

cur.execute("SELECT MAX(timestamp) FROM account_snapshots")
r = cur.fetchone()
print(f"Last account snapshot: {r[0]}")

cur.execute("SELECT MAX(timestamp) FROM decisions")
r = cur.fetchone()
print(f"Last decision: {r[0]}")

print()
print("=== CLOSE REASON BREAKDOWN (ALL TIME) ===")
cur.execute("SELECT close_reason, COUNT(*) as cnt, ROUND(SUM(profit),2) as pnl FROM trades WHERE status='closed' GROUP BY close_reason")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} trades, PnL ${r[2]}")

print()
print("=== ALL TRADES EVER ===")
cur.execute("SELECT id, symbol, direction, profit, status, close_reason, opened_at, closed_at FROM trades ORDER BY id")
for r in cur.fetchall():
    print(f"  #{r[0]} {r[1]} {r[2]} | status={r[3]} profit={r[4]} reason={r[5]}")
    print(f"       opened={r[6]} closed={r[7]}")

db.close()
