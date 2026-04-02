import asyncio
import os
import sys
from datetime import datetime, timezone

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker
from app.db.database import async_session
from app.db.models import Trade
from app.db import crud
from sqlalchemy import select

async def mass_repair():
    print("--- 🚀 MASS P&L RECOVERY START ---")
    connected = await broker.connect()
    if not connected:
        print("❌ Broker connection failed.")
        return

    async with async_session() as db:
        # Find all closed trades with 0 profit from the last few days
        res = await db.execute(
            select(Trade).where(
                (Trade.status == "closed") & (Trade.profit == 0.0) | (Trade.profit == None)
            )
        )
        trades = res.scalars().all()
        print(f"Repairing {len(trades)} trades...")

        for t in trades:
            if not t.external_id:
                continue
                
            print(f"  Syncing Trade {t.id} ({t.symbol})...")
            deals = await broker.get_deals_by_position(t.external_id)
            if deals:
                profit = sum(float(d.get("profit", 0) or 0) for d in deals)
                commissions = sum(float(d.get("commission", 0) or 0) for d in deals)
                swaps = sum(float(d.get("swap", 0) or 0) for d in deals)
                total_profit = profit + commissions + swaps
                
                close_price = 0.0
                for d in deals:
                     if d.get("entry_type") == "DEAL_ENTRY_OUT" or d.get("type", "").endswith("SELL"):
                        close_price = float(d.get("price", 0) or 0)
                        break
                if close_price == 0:
                    close_price = float(deals[-1].get("price", 0) or 0)

                print(f"    ✅ Found Real Profit: ${total_profit:.2f}")
                await crud.close_trade(db, t.id, close_price, total_profit)
                await crud.update_decision_outcome(db, t.id, total_profit > 0)
            else:
                print(f"    ⚠️ No deals found for pos {t.external_id} yet.")

        await db.commit()
    print("--- ✨ MASS RECOVERY COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(mass_repair())
