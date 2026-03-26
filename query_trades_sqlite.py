
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import traceback

# Use SQLite since the file is growing
DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def main():
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            print("Successfully connected to SQLite.")
            
            # Get last 20 trades
            print("\n=== Recent Trades ===")
            result = await conn.execute(text("SELECT id, symbol, direction, volume, open_price, close_price, profit, opened_at, closed_at FROM trades ORDER BY opened_at DESC LIMIT 20"))
            trades = result.fetchall()
            
            print(f"{'ID':<5} {'Symbol':<10} {'Dir':<5} {'Vol':<5} {'Open':<10} {'Close':<10} {'Profit':<10} {'Opened At':<20}")
            for t in trades:
                opened_at_str = t.opened_at if isinstance(t.opened_at, str) else t.opened_at.strftime("%Y-%m-%d %H:%M") if t.opened_at else "N/A"
                profit_str = f"{t.profit:.2f}" if t.profit is not None else "OPEN"
                print(f"{t.id:<5} {t.symbol:<10} {t.direction:<5} {t.volume:<5} {t.open_price:<10.5f} {t.close_price if t.close_price else 0:<10.5f} {profit_str:<10} {opened_at_str:<20}")

            # Total P&L
            result = await conn.execute(text("SELECT SUM(profit) FROM trades WHERE status = 'closed'"))
            total_pnl = result.scalar() or 0
            print(f"\nTotal P&L: {total_pnl:.2f}")

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
