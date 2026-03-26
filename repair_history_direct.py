
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.broker.metaapi_client import broker

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def repair_direct():
    print("🔧 Starting Direct Trade History Repair...")
    await broker.connect()

    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, symbol, external_id FROM trades WHERE status = 'closed' AND profit = 0.0"))
        trades = res.fetchall()
        
        if not trades:
            print("✅ No trades found to fix.")
            return

        print(f"Checking {len(trades)} trades directly via position ID...")
        success_count = 0
        
        for tid, symbol, ext_id in trades:
            if not ext_id: continue
            
            print(f"  Fetching deals for Position {ext_id} ({symbol})...")
            # Try direct endpoint
            deals = await broker._get(f"/history-deals/position/{ext_id}")
            
            if deals and isinstance(deals, list) and len(deals) > 0:
                # MT5: Usually 2 deals (Entry, Exit). We sum them.
                total_profit = 0.0
                close_price = 0.0
                
                for d in deals:
                    # In MT5, only the 'DEAL_ENTRY_OUT' or 'DEAL_ENTRY_INOUT' deal has the profit
                    total_profit += d.get("profit", 0.0) + d.get("swap", 0.0) + d.get("commission", 0.0)
                    if d.get("entryType") in ["DEAL_ENTRY_OUT", "DEAL_ENTRY_INOUT"]:
                        close_price = d.get("price", 0.0)
                
                # If we still have 0.0 for close price, just take the last deal's price
                if close_price == 0.0 and len(deals) > 0:
                    close_price = deals[-1].get("price", 0.0)

                print(f"    ✨ Found! Profit: ${total_profit:.2f}, Close Price: {close_price}")
                
                await conn.execute(
                    text("UPDATE trades SET profit = :p, close_price = :cp WHERE id = :id"),
                    {"p": total_profit, "cp": close_price, "id": tid}
                )
                await conn.execute(
                    text("UPDATE decisions SET was_profitable = :wp WHERE trade_id = :id"),
                    {"wp": total_profit > 0, "id": tid}
                )
                success_count += 1
            else:
                print(f"    ❌ No deals found for position {ext_id}.")

        if success_count > 0:
            await conn.commit()
            print(f"🚀 Repaired {success_count} trades!")
        else:
            print("No trades were repaired.")

    await engine.dispose()
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(repair_direct())
