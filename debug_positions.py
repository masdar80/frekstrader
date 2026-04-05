import asyncio
import os
from app.core.broker.metaapi_client import broker
from app.utils.logger import logger

async def main():
    print("--- 🔍 Debugging Broker Connection ---")
    success = await broker.connect()
    print(f"Connected: {success}")
    print(f"Token: {os.getenv('METAAPI_TOKEN')[:10]}...")
    print(f"Account ID: {os.getenv('METAAPI_ACCOUNT_ID')}")
    
    if success:
        print("Fetching account info...")
        info = await broker.get_account_info(use_cache=False)
        print(f"Equity: {info.get('equity')}")
        print(f"Balance: {info.get('balance')}")
        
        print("Fetching positions...")
        positions = await broker.get_positions()
        print(f"Positions Count: {len(positions)}")
        for i, p in enumerate(positions):
            print(f"  [{i}] {p.get('symbol')} {p.get('type')} volume={p.get('volume')} id={p.get('id')}")
        
        print("Fetching open trades from DB...")
        from app.db.database import async_session
        from app.db import crud
        async with async_session() as db:
            open_trades = await crud.get_open_trades(db)
            print(f"DB Open Trades Count: {len(open_trades)}")
    else:
        print("❌ BROKER FAILED TO CONNECT")

if __name__ == "__main__":
    asyncio.run(main())
