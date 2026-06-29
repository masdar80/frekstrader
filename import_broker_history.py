import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker
from app.db.database import async_session, Base, engine
from app.db.models import Trade

async def import_history():
    # Recreate tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("--- 🔄 IMPORTING REAL BROKER HISTORY ---")
    connected = await broker.connect()
    if not connected:
        print("❌ Failed to connect to broker.")
        return

    # Fetch 30 days of history
    print("Fetching history deals from MetaAPI...")
    deals = await broker.get_history(days=30)
    print(f"Total deals retrieved: {len(deals)}")

    if not deals:
        print("No historical deals found at broker.")
        await broker.disconnect()
        return

    # Group deals by position_id
    positions = {}
    for d in deals:
        pid = d.get("position_id")
        if not pid:
            continue
        if pid not in positions:
            positions[pid] = []
        positions[pid].append(d)

    print(f"Grouped into {len(positions)} unique positions.")

    async with async_session() as db:
        imported_count = 0
        for pid, p_deals in positions.items():
            # Check if this trade is already in the database
            res = await db.execute(select(Trade).where(Trade.external_id == pid))
            existing = res.scalar_one_or_none()
            if existing:
                print(f"  Trade {pid} already in DB. Skipping.")
                continue

            # Sort deals by time to identify entry and exit
            p_deals.sort(key=lambda x: x.get("time", ""))

            entry_deal = None
            exit_deal = None
            
            for d in p_deals:
                if d.get("entry_type") == "DEAL_ENTRY_IN":
                    entry_deal = d
                elif d.get("entry_type") == "DEAL_ENTRY_OUT":
                    exit_deal = d

            # If no DEAL_ENTRY_IN, default to first deal
            if not entry_deal:
                entry_deal = p_deals[0]
            # If no DEAL_ENTRY_OUT but we have multiple deals, last one is exit
            if not exit_deal and len(p_deals) > 1:
                exit_deal = p_deals[-1]

            symbol = entry_deal.get("symbol")
            p_type = entry_deal.get("type", "")
            direction = "BUY" if "BUY" in p_type else "SELL"
            volume = entry_deal.get("volume", 0.01)
            open_price = entry_deal.get("price")
            sl = entry_deal.get("stop_loss")
            tp = entry_deal.get("take_profit")

            close_price = exit_deal.get("price") if exit_deal else open_price
            
            # Sum profit, commission and swap for all deals in this position
            profit = sum(d.get("profit", 0.0) + d.get("swap", 0.0) + d.get("commission", 0.0) for d in p_deals)

            opened_at_str = entry_deal.get("time")
            opened_at = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00")) if opened_at_str else datetime.utcnow()

            closed_at_str = exit_deal.get("time") if exit_deal else None
            closed_at = datetime.fromisoformat(closed_at_str.replace("Z", "+00:00")) if closed_at_str else opened_at

            # Close reason classification
            close_reason = "manual"
            if exit_deal:
                # Compare close price with stop_loss / take_profit
                is_jpy = "JPY" in symbol
                threshold = 0.02 if is_jpy else 0.0002
                if tp and abs(close_price - tp) <= threshold:
                    close_reason = "tp"
                elif sl and abs(close_price - sl) <= threshold:
                    close_reason = "sl"

            status = "closed" if exit_deal else "open"

            new_trade = Trade(
                external_id=pid,
                symbol=symbol,
                direction=direction,
                volume=volume,
                open_price=open_price,
                close_price=close_price if status == "closed" else None,
                stop_loss=sl,
                take_profit=tp,
                profit=profit if status == "closed" else None,
                status=status,
                opened_at=opened_at,
                closed_at=closed_at if status == "closed" else None,
                close_reason=close_reason if status == "closed" else None,
                trading_mode="recovered",
                metadata_json={"imported": True, "import_time": datetime.utcnow().isoformat()}
            )
            db.add(new_trade)
            print(f"  ➕ Importing {direction} {volume} {symbol} (Position ID: {pid}) P&L: ${profit:.2f} (Reason: {close_reason})")
            imported_count += 1

        if imported_count > 0:
            await db.commit()
            print(f"✅ Successfully imported {imported_count} trades into SQLite database!")
        else:
            print("No new trades needed importing.")

    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(import_history())
