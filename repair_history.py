
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.broker.metaapi_client import broker
from app.config import settings

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def repair():
    print("🔧 Starting Trade History Repair...")
    
    # 1. Connect to Broker
    print("Connecting to MetaAPI...")
    connected = await broker.connect()
    if not connected:
        print("❌ Failed to connect to MetaAPI. Aborting.")
        return

    # 2. Get history from Broker (last 7 days to be safe)
    print("Fetching last 7 days of history deals from MetaAPI...")
    history_deals = await broker.get_history(days=7)
    print(f"  Found {len(history_deals)} deals in history.")

    # 3. Connect to DB and find trades to fix
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, symbol, external_id, profit FROM trades WHERE status = 'closed' AND profit = 0.0"))
        trades_to_fix = res.fetchall()
        
        if not trades_to_fix:
            print("✅ No trades found with $0.00 profit to fix.")
            return

        print(f"Found {len(trades_to_fix)} trades to potentially repair.")
        
        fixed_count = 0
        for trade_id, symbol, ext_id, current_profit in trades_to_fix:
            if not ext_id:
                print(f"  Trade {trade_id} ({symbol}) has no external_id. Skipping.")
                continue
                
            # Find matching deal in history
            deal = next((d for d in history_deals if d.get("position_id") == ext_id), None)
            
            if deal:
                real_profit = deal.get("profit", 0.0) + deal.get("swap", 0.0) + deal.get("commission", 0.0)
                real_close_price = deal.get("price", 0.0)
                
                print(f"  ✨ Repairing Trade {trade_id} ({symbol}): Old P&L $0.00 -> New P&L ${real_profit:.2f}")
                
                await conn.execute(
                    text("UPDATE trades SET profit = :p, close_price = :cp WHERE id = :id"),
                    {"p": real_profit, "cp": real_close_price, "id": trade_id}
                )
                
                # Also update decision outcome
                await conn.execute(
                    text("UPDATE decisions SET was_profitable = :wp WHERE trade_id = :id"),
                    {"wp": real_profit > 0, "id": trade_id}
                )
                fixed_count += 1
            else:
                print(f"  ⚠️ Could not find history deal for Position ID {ext_id} in fetched history.")

        if fixed_count > 0:
            await conn.commit()
            print(f"🚀 Successfully repaired {fixed_count} trade records!")
        else:
            print("No matching deals found in history to apply.")

    await engine.dispose()
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(repair())
