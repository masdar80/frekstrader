"""Quick DB stats check for backtesting feasibility."""
import sqlite3

conn = sqlite3.connect('foreks.db')
cur = conn.cursor()

# Tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cur.fetchall()])

# Trades
cur.execute("SELECT COUNT(*) FROM trades")
print(f"\nTotal trades: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM trades WHERE status='closed'")
print(f"Closed trades: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM trades WHERE status='open'")
print(f"Open trades: {cur.fetchone()[0]}")
cur.execute("SELECT MIN(opened_at), MAX(opened_at) FROM trades")
r = cur.fetchone()
print(f"Trade date range: {r[0]} to {r[1]}")

# Trade breakdown by trading mode
cur.execute("SELECT trading_mode, COUNT(*), SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END), SUM(profit) FROM trades WHERE status='closed' GROUP BY trading_mode")
print("\nClosed trades by mode:")
for row in cur.fetchall():
    mode, count, wins, total_profit = row
    wr = (wins/count*100) if count > 0 else 0
    print(f"  {mode}: {count} trades, {wins} wins ({wr:.1f}%), Total P&L: ${total_profit:.2f}")

# Trade breakdown by symbol
cur.execute("SELECT symbol, COUNT(*), SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END), SUM(profit) FROM trades WHERE status='closed' GROUP BY symbol")
print("\nClosed trades by symbol:")
for row in cur.fetchall():
    sym, count, wins, total_profit = row
    wr = (wins/count*100) if count > 0 else 0
    print(f"  {sym}: {count} trades, {wins} wins ({wr:.1f}%), Total P&L: ${total_profit:.2f}")

# Decisions
cur.execute("SELECT COUNT(*) FROM decisions")
print(f"\nTotal decisions: {cur.fetchone()[0]}")
cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM decisions")
r = cur.fetchone()
print(f"Decision date range: {r[0]} to {r[1]}")

# Decision breakdown
cur.execute("SELECT action, COUNT(*) FROM decisions GROUP BY action")
print("\nDecisions by action:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Signals
cur.execute("SELECT COUNT(*) FROM signals")
print(f"\nTotal signals: {cur.fetchone()[0]}")
cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM signals")
r = cur.fetchone()
print(f"Signal date range: {r[0]} to {r[1]}")

# Signal sources
cur.execute("SELECT source, COUNT(*) FROM signals GROUP BY source")
print("\nSignals by source:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Snapshots
cur.execute("SELECT COUNT(*) FROM account_snapshots")
print(f"\nTotal snapshots: {cur.fetchone()[0]}")
cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM account_snapshots")
r = cur.fetchone()
print(f"Snapshot date range: {r[0]} to {r[1]}")

# Equity progression
cur.execute("SELECT timestamp, balance, equity FROM account_snapshots ORDER BY timestamp ASC LIMIT 5")
print("\nFirst 5 snapshots (equity):")
for row in cur.fetchall():
    print(f"  {row[0]}: Balance={row[1]}, Equity={row[2]}")

cur.execute("SELECT timestamp, balance, equity FROM account_snapshots ORDER BY timestamp DESC LIMIT 5")
print("\nLast 5 snapshots (equity):")
for row in cur.fetchall():
    print(f"  {row[0]}: Balance={row[1]}, Equity={row[2]}")

# Recent trade details
cur.execute("""SELECT symbol, direction, opened_at, closed_at, profit, trading_mode, close_reason 
               FROM trades WHERE status='closed' ORDER BY closed_at DESC LIMIT 20""")
print("\nLast 20 closed trades:")
for row in cur.fetchall():
    print(f"  {row[0]} {row[1]} | Opened: {row[2]} | Closed: {row[3]} | P&L: ${row[4]:.2f} | Mode: {row[5]} | Reason: {row[6]}")

# Average trade duration
cur.execute("""SELECT AVG(julianday(closed_at) - julianday(opened_at)) * 24 as avg_hours 
               FROM trades WHERE status='closed' AND closed_at IS NOT NULL AND opened_at IS NOT NULL""")
avg = cur.fetchone()[0]
print(f"\nAverage trade duration: {avg:.1f} hours" if avg else "\nAverage trade duration: N/A")

conn.close()
