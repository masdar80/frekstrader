import asyncio
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

from app.db.database import async_session
from app.db.models import Trade
from sqlalchemy import select

async def run():
    async with async_session() as db:
        res = await db.execute(select(Trade).where(Trade.status == 'open'))
        trades = res.scalars().all()
        print(f"Open trades in DB: {len(trades)}")
        for t in trades:
            print(f"  - {t.id}: {t.symbol} ({t.external_id})")

if __name__ == "__main__":
    asyncio.run(run())
