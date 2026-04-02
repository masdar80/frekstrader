import asyncio
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker
from app.db.database import async_session
from app.db.models import Trade
from sqlalchemy import select

async def investigate():
    print("--- INVESTIGATION START ---")
    
    # 1. Check Broker State
    print("\n[1] Checking Broker Positions...")
    connected = await broker.connect()
    if not connected:
        print("Failed to connect to MetaAPI.")
        return
    
    broker_positions = await broker.get_positions(use_cache=False)
    print(f"Total positions at Broker: {len(broker_positions)}")
    for p in broker_positions:
        print(f"  - ID: {p.get('id')}, Symbol: {p.get('symbol')}, Type: {p.get('type')}, Profit: {p.get('profit')}")
    
    # 2. Check DB State
    print("\n[2] Checking Database Trades...")
    async with async_session() as db:
        # All trades
        result = await db.execute(select(Trade))
        all_trades = result.scalars().all()
        print(f"Total trades in DB: {len(all_trades)}")
        
        open_trades = [t for t in all_trades if t.status == 'open']
        print(f"Open trades in DB: {len(open_trades)}")
        for t in open_trades:
            print(f"  - DB_ID: {t.id}, EXT_ID: {t.external_id}, Symbol: {t.symbol}")
            
        # Check if broker IDs are in DB but closed
        broker_ids = {str(p.get('id')) for p in broker_positions}
        closed_matches = [t for t in all_trades if t.status == 'closed' and str(t.external_id) in broker_ids]
        if closed_matches:
            print(f"\n[!] WARNING: Found {len(closed_matches)} trades in DB marked as CLOSED but still OPEN at broker!")
            for t in closed_matches:
                print(f"  - DB_ID: {t.id}, EXT_ID: {t.external_id}, Symbol: {t.symbol}")

    await broker.disconnect()
    print("\n--- INVESTIGATION END ---")

if __name__ == "__main__":
    asyncio.run(investigate())
