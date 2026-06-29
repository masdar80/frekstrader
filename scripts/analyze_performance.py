import asyncio
import os
import sys
import pandas as pd
from sqlalchemy import select

# Add parent directory to path to allow importing app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.database import async_session
from app.db.models import Trade

async def run_analysis():
    print("--- ForeksTrader Performance Analyzer ---")
    async with async_session() as db:
        # Load all closed trades
        result = await db.execute(select(Trade).where(Trade.status == 'closed'))
        trades = result.scalars().all()
        
        if not trades:
            print("No closed trades found.")
            return

        print(f"Loaded {len(trades)} closed trades.")

        data = []
        for t in trades:
            data.append({
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction,
                "profit": t.profit or 0.0,
                "profit_pips": t.profit_pips or 0.0,
                "opened_at": t.opened_at,
                "close_reason": t.close_reason,
                "hour": t.opened_at.hour if t.opened_at else None,
                "day_of_week": t.opened_at.weekday() if t.opened_at else None,
            })
            
        df = pd.DataFrame(data)
        df["win"] = df["profit"] > 0
        
        print("\n--- Overall Performance ---")
        print(f"Total Trades: {len(df)}")
        print(f"Win Rate: {(df['win'].mean() * 100):.2f}%")
        print(f"Total Profit: ${df['profit'].sum():.2f}")
        
        print("\n--- By Symbol ---")
        symbol_stats = df.groupby("symbol").agg(
            trades=("id", "count"),
            win_rate=("win", "mean"),
            profit=("profit", "sum")
        )
        symbol_stats["win_rate"] = (symbol_stats["win_rate"] * 100).round(2)
        symbol_stats["profit"] = symbol_stats["profit"].round(2)
        print(symbol_stats.to_string())

        print("\n--- By Direction ---")
        dir_stats = df.groupby("direction").agg(
            trades=("id", "count"),
            win_rate=("win", "mean"),
            profit=("profit", "sum")
        )
        dir_stats["win_rate"] = (dir_stats["win_rate"] * 100).round(2)
        dir_stats["profit"] = dir_stats["profit"].round(2)
        print(dir_stats.to_string())

        print("\n--- By Hour of Day ---")
        hour_stats = df.groupby("hour").agg(
            trades=("id", "count"),
            win_rate=("win", "mean"),
            profit=("profit", "sum")
        )
        hour_stats["win_rate"] = (hour_stats["win_rate"] * 100).round(2)
        hour_stats["profit"] = hour_stats["profit"].round(2)
        print(hour_stats.to_string())
        
        print("\n--- By Close Reason ---")
        reason_stats = df.groupby("close_reason").agg(
            trades=("id", "count"),
            win_rate=("win", "mean"),
            profit=("profit", "sum")
        )
        reason_stats["win_rate"] = (reason_stats["win_rate"] * 100).round(2)
        reason_stats["profit"] = reason_stats["profit"].round(2)
        print(reason_stats.to_string())

if __name__ == "__main__":
    asyncio.run(run_analysis())
