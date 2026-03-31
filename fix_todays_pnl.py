import asyncio
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

# Ensure we use localhost for the repair script
os.environ["DATABASE_URL"] = "postgresql+asyncpg://foreks:foreks_secret@localhost:5432/foreksdb"

from app.core.broker.metaapi_client import broker
from app.db.database import async_session
from app.db import crud
from sqlalchemy import text

async def fix_pnl():
    print("Connecting to MetaAPI...")
    # The broker.connect() now uses the fixed PROVISIONING_URL from the patched metaapi_client.py
    connected = await broker.connect()
    if not connected:
        print("Failed to connect to MetaAPI. Check your token/network.")
        return
    
    print("Fetching last 3 days of deals...")
    history = await broker.get_history(days=3)
    print(f"Found {len(history)} deals in history.")
    
    async with async_session() as db:
        # Get trades that are closed but have 0 profit
        result = await db.execute(text("SELECT id, external_id, symbol FROM trades WHERE status = 'closed' AND profit = 0"))
        trades_to_fix = result.fetchall()
        
        if not trades_to_fix:
            print("No trades found with $0 profit to fix.")
        else:
            print(f"Checking {len(trades_to_fix)} trades...")
            for t_id, ext_id, symbol in trades_to_fix:
                print(f"Trade {t_id} ({symbol}, ext:{ext_id}):")
                
                matching = [d for d in history if str(d.get('position_id')) == str(ext_id)]
                
                if matching:
                    total_profit = sum(d.get('profit', 0) + d.get('swap', 0) + d.get('commission', 0) for d in matching)
                    close_price = 0
                    for d in matching:
                        if d.get('entry_type') == 'DEAL_ENTRY_OUT':
                            close_price = d.get('price', 0)
                    if not close_price:
                        close_price = matching[-1].get('price', 0)
                    
                    print(f"  -> SUCCESS! Found {len(matching)} deals. True Profit: ${total_profit:.2f}, Close Price: {close_price}")
                    await crud.close_trade(db, t_id, close_price, total_profit)
                    await db.commit()
                else:
                    print(f"  -> Still no deals found for position {ext_id} in current 3-day history.")

    await broker.disconnect()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(fix_pnl())
