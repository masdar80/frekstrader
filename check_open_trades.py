import os
# Set this BEFORE any app imports
os.environ["DATABASE_URL"] = "postgresql+asyncpg://foreks:foreks_secret@127.0.0.1:5432/foreksdb"

import asyncio
import sys

# Add root to path
sys.path.append(os.getcwd())

from app.db.database import async_session
from app.db.models import Trade
from sqlalchemy import select

async def check():
    async with async_session() as db:
        res = await db.execute(select(Trade).where(Trade.status == 'open'))
        open_trades = res.scalars().all()
        print(f"Total Open Trades in DB: {len(open_trades)}")
        for t in open_trades:
            print(f"  - ID: {t.id}, EXT: {t.external_id}, Sym: {t.symbol}, Opened: {t.opened_at}")

if __name__ == "__main__":
    asyncio.run(check())
