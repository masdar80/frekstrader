import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app.db.database import async_session
from app.db.models import AccountSnapshot, Trade

async def check_logs():
    async with async_session() as db:
        # Check snapshot timestamps for the last 7 days
        last_week = datetime.utcnow() - timedelta(days=7)
        
        stmt = select(func.min(AccountSnapshot.timestamp), func.max(AccountSnapshot.timestamp), func.count(AccountSnapshot.id)).where(AccountSnapshot.timestamp >= last_week)
        result = await db.execute(stmt)
        min_ts, max_ts, count = result.first()
        
        print("--- Snapshot Check ---")
        print(f"Snapshots found: {count}")
        if count > 0:
            print(f"Oldest in last 7 days: {min_ts}")
            print(f"Newest in last 7 days: {max_ts}")

        # Check trades created in the last 7 days
        trade_stmt = select(func.min(Trade.opened_at), func.max(Trade.opened_at), func.count(Trade.id)).where(Trade.opened_at >= last_week)
        trade_result = await db.execute(trade_stmt)
        min_trade, max_trade, count_trade = trade_result.first()
        print("\n--- Trade Check ---")
        print(f"Trades opened in last 7 days: {count_trade}")

if __name__ == "__main__":
    asyncio.run(check_logs())
