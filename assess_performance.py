import sqlite3
import json
from datetime import datetime, timedelta

db = sqlite3.connect(r'd:\foreks\foreks.db')
db.row_factory = sqlite3.Row
cur = db.cursor()

print("=== TABLE LIST ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
for t in tables:
    print(" -", t["name"])

print()
print("=== TOTAL TRADES IN DB ===")
cur.execute("SELECT COUNT(*) as cnt, status FROM trades GROUP BY status")
for r in cur.fetchall():
    print(f"  {r['status']}: {r['cnt']}")

print()
print("=== ALL-TIME PERFORMANCE SUMMARY ===")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN profit = 0 THEN 1 ELSE 0 END) as breakeven,
        ROUND(SUM(profit),2) as total_pnl,
        ROUND(AVG(profit),2) as avg_pnl,
        ROUND(MAX(profit),2) as best_win,
        ROUND(MIN(profit),2) as worst_loss
    FROM trades WHERE status='closed'
""")
r = cur.fetchone()
if r and r["total"] > 0:
    wr = r["wins"] / r["total"] * 100
    print(f"  Total Closed: {r['total']}")
    print(f"  Wins/Losses/BE: {r['wins']} / {r['losses']} / {r['breakeven']}")
    print(f"  Win Rate: {wr:.1f}%")
    print(f"  Total PnL: ${r['total_pnl']}")
    print(f"  Avg Per Trade: ${r['avg_pnl']}")
    print(f"  Best Win: ${r['best_win']}")
    print(f"  Worst Loss: ${r['worst_loss']}")

print()
print("=== LAST 30 DAYS CLOSED TRADES ===")
cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
cur.execute("""
    SELECT symbol, direction, profit, close_reason, closed_at, open_price, close_price, volume, strategy_version
    FROM trades WHERE status='closed' AND closed_at >= ? ORDER BY closed_at DESC
""", (cutoff,))
rows = cur.fetchall()
total_pnl = 0
wins = 0
losses = 0
close_reasons = {}
for r in rows:
    p = r["profit"] or 0
    total_pnl += p
    if p > 0: wins += 1
    elif p < 0: losses += 1
    cr = r["close_reason"] or "unknown"
    close_reasons[cr] = close_reasons.get(cr, 0) + 1
    pnl_str = f"+${p:.2f}" if p > 0 else f"-${abs(p):.2f}"
    print(f"  {r['closed_at'][:16]} | {r['symbol']} {r['direction']} v{r['volume']} | PnL:{pnl_str} | {cr}")

print()
print(f"  Last 30d: {wins}W / {losses}L | PnL: ${total_pnl:.2f}")
if wins+losses > 0:
    print(f"  Win Rate: {wins/(wins+losses)*100:.1f}%")
print(f"  Close Reasons: {close_reasons}")

print()
print("=== DECISIONS TABLE (last 20) ===")
try:
    cur.execute("""
        SELECT timestamp, symbol, action, confidence, trading_mode, was_profitable
        FROM decisions ORDER BY timestamp DESC LIMIT 20
    """)
    decs = cur.fetchall()
    for d in decs:
        print(f"  {d['timestamp'][:16]} | {d['symbol']} {d['action']} | conf={d['confidence']} | profitable={d['was_profitable']}")
except Exception as e:
    print(f"  (no decisions table or error: {e})")

print()
print("=== ACCOUNT SNAPSHOTS (last 15) ===")
cur.execute("SELECT timestamp, balance, equity, daily_pnl, drawdown_pct, open_positions FROM account_snapshots ORDER BY timestamp DESC LIMIT 15")
snaps = cur.fetchall()
for r in snaps:
    print(f"  {r['timestamp'][:16]} | Bal:${r['balance']:.2f} | Eq:${r['equity']:.2f} | DailyPnL:{r['daily_pnl']} | DD:{r['drawdown_pct']}% | Open:{r['open_positions']}")

print()
print("=== FIRST VS LATEST SNAPSHOT (equity growth) ===")
cur.execute("SELECT * FROM account_snapshots ORDER BY timestamp ASC LIMIT 1")
first = cur.fetchone()
cur.execute("SELECT * FROM account_snapshots ORDER BY timestamp DESC LIMIT 1")
last = cur.fetchone()
if first and last:
    diff = last["equity"] - first["equity"]
    pct = (diff / first["equity"]) * 100 if first["equity"] > 0 else 0
    print(f"  First: {first['timestamp'][:10]} Equity=${first['equity']:.2f}")
    print(f"  Last:  {last['timestamp'][:10]}  Equity=${last['equity']:.2f}")
    print(f"  Growth: ${diff:.2f} ({pct:.2f}%)")

print()
print("=== OPEN POSITIONS NOW ===")
cur.execute("SELECT symbol, direction, volume, open_price, stop_loss, take_profit, opened_at, close_reason FROM trades WHERE status='open'")
for r in cur.fetchall():
    print(f"  {r['symbol']} {r['direction']} v{r['volume']} @ {r['open_price']} | SL:{r['stop_loss']} TP:{r['take_profit']} | since {r['opened_at']}")

db.close()
