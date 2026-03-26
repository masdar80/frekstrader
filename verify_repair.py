
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def check():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, symbol, profit, closed_at FROM trades WHERE id IN (2, 3)"))
        rows = res.fetchall()
        for r in rows:
            print(f"Trade {r[0]} ({r[1]}): Profit ${r[2]:.2f} (Closed: {r[3]})")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
