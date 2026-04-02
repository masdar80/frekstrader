import asyncio
import os
import sys
from datetime import datetime, timezone

# Add root to path
sys.path.append(os.getcwd())

from app.config import settings
from app.core.broker.metaapi_client import broker
from app.db.database import async_session
from app.db.models import Trade
from sqlalchemy import select, update

# Override DATABASE_URL for local execution if it points to 'db'
if "@db:" in settings.database_url:
    os.environ["DATABASE_URL"] = settings.database_url.replace("@db:", "@localhost:")
    print(f"🔄 Overriding DATABASE_URL for local execution: {os.environ['DATABASE_URL']}")

async def sync():
    print("--- 🔄 SYNC START: Restoring Trade Visibility ---")
    
    # 1. Connect to Broker
    print("[1] Connecting to MetaAPI...")
    connected = await broker.connect()
    if not connected:
        print("❌ Failed to connect to MetaAPI.")
        return
    
    broker_positions = await broker.get_positions(use_cache=False)
    print(f"📡 Found {len(broker_positions)} open positions at Broker.")
    
    # 2. Sync to DB
    async with async_session() as db:
        for p in broker_positions:
            ext_id = str(p.get("id"))
            symbol = p.get("symbol")
            p_type = p.get("type")
            direction = "BUY" if "BUY" in p_type else "SELL"
            volume = p.get("volume", 0.01)
            open_price = p.get("openPrice", 0.0)
            sl = p.get("stopLoss")
            tp = p.get("takeProfit")
            
            # Check if exists
            result = await db.execute(select(Trade).where(Trade.external_id == ext_id))
            existing = result.scalar_one_or_none()
            
            if existing:
                if existing.status != "open":
                    print(f"  ⚠️ Trade {ext_id} ({symbol}) exists as '{existing.status}'. Reactivating to 'open'...")
                    existing.status = "open"
                    existing.close_price = None
                    existing.closed_at = None
                    existing.profit = None
                else:
                    print(f"  ✅ Trade {ext_id} ({symbol}) is already correctly marked as 'open' in DB.")
            else:
                print(f"  ➕ Trade {ext_id} ({symbol}) missing from DB. Creating new record...")
                new_trade = Trade(
                    external_id=ext_id,
                    symbol=symbol,
                    direction=direction,
                    volume=volume,
                    open_price=open_price,
                    stop_loss=sl,
                    take_profit=tp,
                    status="open",
                    opened_at=datetime.now(timezone.utc), # We don't have exact time easily but this is better than nothing
                    trading_mode="recovered",
                    metadata_json={"recovered": True, "sync_at": datetime.now(timezone.utc).isoformat()}
                )
                db.add(new_trade)
        
        await db.commit()
    
    await broker.disconnect()
    print("\n--- ✅ SYNC COMPLETE: Dashboard should now show all positions. ---")

if __name__ == "__main__":
    asyncio.run(sync())
