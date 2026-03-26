
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, symbol, direction, status, profit, opened_at, closed_at FROM trades WHERE id IN (2, 3)"))
        for r in res:
            print(r)

if __name__ == "__main__":
    asyncio.run(main())
