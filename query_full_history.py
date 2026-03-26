
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import traceback

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def main():
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            # All trades
            print("\n=== All Trades ===")
            result = await conn.execute(text("SELECT * FROM trades"))
            keys = result.keys()
            for r in result:
                print(dict(zip(keys, r)))

            # Recent decisions (last 5)
            print("\n=== Recent Decisions ===")
            result = await conn.execute(text("SELECT id, symbol, action, timestamp, reasoning FROM decisions ORDER BY timestamp DESC LIMIT 5"))
            keys = result.keys()
            for r in result:
                print(dict(zip(keys, r)))

            # Account snapshots (last 5)
            print("\n=== Recent Snapshots ===")
            result = await conn.execute(text("SELECT * FROM account_snapshots ORDER BY timestamp DESC LIMIT 5"))
            keys = result.keys()
            for r in result:
                print(dict(zip(keys, r)))

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
