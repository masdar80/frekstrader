
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def main():
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            print("--- TRADES ---")
            res = await conn.execute(text("SELECT id, symbol, direction, status, profit, opened_at, closed_at, trading_mode FROM trades ORDER BY id DESC LIMIT 10"))
            for r in res:
                print(r)
            
            print("\n--- DECISIONS FOR TRADES 2 & 3 ---")
            res = await conn.execute(text("SELECT id, trade_id, symbol, action, reasoning FROM decisions WHERE trade_id IN (2, 3)"))
            for r in res:
                print(r)

            print("\n--- RECENT SNAPSHOTS (24H) ---")
            res = await conn.execute(text("SELECT timestamp, equity, balance, drawdown_pct FROM account_snapshots ORDER BY timestamp DESC LIMIT 5"))
            for r in res:
                print(r)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
