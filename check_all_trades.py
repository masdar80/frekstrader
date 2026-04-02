import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://foreks:foreks_secret@127.0.0.1:5432/foreksdb"

import asyncio
import sys

# Add root to path
sys.path.append(os.getcwd())

from app.db.database import async_session
from app.db.models import Trade
from sqlalchemy import select, desc

async def check():
    async with async_session() as db:
        res = await db.execute(select(Trade).order_by(desc(Trade.opened_at)).limit(20))
        trades = res.scalars().all()
        print(f"Total Trades found: {len(trades)}")
        for t in trades:
            print(f"  - ID: {t.id}, EXT: {t.external_id}, Sym: {t.symbol}, Status: {t.status}, Profit: {t.profit}, Closed: {t.closed_at}")

if __name__ == "__main__":
    asyncio.run(check())
