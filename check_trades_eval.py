import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('foreks.db')
cur = conn.cursor()

# Check the most recent snapshots (collected by the current running bot)
print("=== LATEST 3 SNAPSHOTS (from today's bot) ===")
cur.execute("""
    SELECT id, symbol, timestamp, indicators_json 
    FROM feature_snapshots 
    ORDER BY id DESC LIMIT 3
""")
for row in cur.fetchall():
    snap_id, symbol, ts, raw = row
    print(f"\nSnap ID {snap_id} | {symbol} | {ts}")
    if raw:
        d = json.loads(raw) if isinstance(raw, str) else raw
        top_keys = list(d.keys())[:5]
        print(f"  Top-level keys: {top_keys}")
        first_key = list(d.keys())[0]
        print(f"  [{first_key}] -> {d[first_key]}")

# Compare with oldest snapshots
print("\n=== OLDEST 3 SNAPSHOTS (old format) ===")
cur.execute("""
    SELECT id, symbol, timestamp, indicators_json 
    FROM feature_snapshots 
    ORDER BY id ASC LIMIT 3
""")
for row in cur.fetchall():
    snap_id, symbol, ts, raw = row
    print(f"\nSnap ID {snap_id} | {symbol} | {ts}")
    if raw:
        d = json.loads(raw) if isinstance(raw, str) else raw
        top_keys = list(d.keys())[:5]
        print(f"  Top-level keys: {top_keys}")
        first_key = list(d.keys())[0]
        print(f"  [{first_key}] -> {d[first_key]}")

# Count snapshots by format type
print("\n=== FORMAT BREAKDOWN (last 1000 vs all) ===")
TIMEFRAMES = {'15m', '1h', '4h', '1d', '30m', 'H1', 'H4', 'D1', 'M15'}
cur.execute("SELECT indicators_json FROM feature_snapshots ORDER BY id DESC LIMIT 1000")
new_correct = 0
new_old = 0
for (raw,) in cur.fetchall():
    if raw:
        d = json.loads(raw) if isinstance(raw, str) else raw
        if set(d.keys()) & TIMEFRAMES:
            new_correct += 1
        else:
            new_old += 1
print(f"  Last 1000: correct format={new_correct}, old format={new_old}")

conn.close()
