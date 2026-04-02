import asyncio
import os
import sys
from datetime import datetime, timezone

# Add root to path
sys.path.append(os.getcwd())

from app.db.database import async_session
from app.db.models import Trade
from app.config import settings
from sqlalchemy import select

# Override DATABASE_URL for local execution
if "@db:" in settings.database_url:
    os.environ["DATABASE_URL"] = settings.database_url.replace("@db:", "@127.0.0.1:")

POSITIONS = [
    {"id": "56011396572", "symbol": "AUDUSD", "dir": "SELL", "vol": 0.1},
    {"id": "56036385789", "symbol": "AUDUSD", "dir": "SELL", "vol": 0.1},
    {"id": "56036429791", "symbol": "AUDUSD", "dir": "SELL", "vol": 0.1},
    {"id": "56036483938", "symbol": "AUDUSD", "dir": "SELL", "vol": 0.1},
    {"id": "56036517109", "symbol": "AUDUSD", "dir": "SELL", "vol": 0.1},
    {"id": "56024645411", "symbol": "EURUSD", "dir": "BUY", "vol": 0.1},
    {"id": "56011503358", "symbol": "USDCHF", "dir": "BUY", "vol": 0.1},
    {"id": "56036390333", "symbol": "USDCHF", "dir": "BUY", "vol": 0.1},
    {"id": "56036431546", "symbol": "USDCHF", "dir": "BUY", "vol": 0.1},
    {"id": "56036485513", "symbol": "USDCHF", "dir": "BUY", "vol": 0.1},
    {"id": "56036519424", "symbol": "USDCHF", "dir": "BUY", "vol": 0.1},
]

async def manual_sync():
    print(f"🔄 Injecting {len(POSITIONS)} positions into database...")
    async with async_session() as db:
        for p in POSITIONS:
            # Check if exists
            res = await db.execute(select(Trade).where(Trade.external_id == p["id"]))
            if res.scalar_one_or_none():
                print(f"  ✅ {p['id']} already in DB.")
                continue
                
            new_trade = Trade(
                external_id=p["id"],
                symbol=p["symbol"],
                direction=p["dir"],
                volume=p["vol"],
                status="open",
                trading_mode="recovered",
                opened_at=datetime.now(timezone.utc),
                metadata_json={"recovered": True}
            )
            db.add(new_trade)
            print(f"  ➕ Added {p['id']} ({p['symbol']})")
        
        await db.commit()
    print("✨ Recovery complete.")

if __name__ == "__main__":
    asyncio.run(manual_sync())
