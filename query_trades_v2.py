
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import traceback

DATABASE_URL = "postgresql+asyncpg://foreks:foreks_secret@db:5432/foreksdb"

async def main():
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            print("Successfully connected to the database.")
            
            # List tables
            print("\n=== Tables ===")
            res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            for r in res:
                print(f"- {r[0]}")
            
            # Query trades with more care
            print("\n=== Recent Closed Trades ===")
            res = await conn.execute(text("SELECT id, symbol, direction, volume, open_price, close_price, profit, opened_at, closed_at FROM trades WHERE status = 'closed' ORDER BY closed_at DESC LIMIT 10"))
            for r in res:
                print(r)
                
            print("\n=== Active Position ===")
            res = await conn.execute(text("SELECT id, symbol, direction, volume, open_price, profit FROM trades WHERE status = 'open'"))
            for r in res:
                print(r)

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
