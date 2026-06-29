import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, asc, desc
from app.db.database import async_session
from app.db.models import Trade, Decision, AccountSnapshot
import pandas as pd

async def analyze():
    async with async_session() as db:
        now = datetime.utcnow()
        one_week_ago = now - timedelta(days=7)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        print(f"--- Analysis Report ---")
        print(f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # 1. Weekly trades
        stmt_week = select(Trade).where(Trade.opened_at >= one_week_ago).order_by(asc(Trade.opened_at))
        result_week = await db.execute(stmt_week)
        week_trades = result_week.scalars().all()
        
        print(f"\n--- Last 7 Days Overview ---")
        print(f"Total Trades Opened: {len(week_trades)}")
        
        closed_trades = [t for t in week_trades if t.status == 'closed']
        open_trades = [t for t in week_trades if t.status == 'open']
        
        print(f"Closed Trades: {len(closed_trades)}")
        print(f"Currently Open Trades: {len(open_trades)}")
        
        if closed_trades:
            profits = [t.profit for t in closed_trades]
            total_pnl = sum(profits)
            wins = len([p for p in profits if p > 0])
            losses = len([p for p in profits if p <= 0])
            print(f"Total PnL: ${total_pnl:.2f}")
            print(f"Win Rate: {(wins/len(closed_trades))*100:.1f}% ({wins}W / {losses}L)")
            print(f"Max Win: ${max(profits):.2f}")
            print(f"Max Loss: ${min(profits):.2f}")
        
        # Breakdown by symbol
        if closed_trades:
            df = pd.DataFrame([{
                'symbol': t.symbol, 
                'profit': t.profit,
                'duration_hrs': (t.closed_at - t.opened_at).total_seconds() / 3600 if t.closed_at else 0,
                'reason': t.close_reason
            } for t in closed_trades])
            
            print("\n--- By Symbol ---")
            grouped = df.groupby('symbol').agg(
                trades=('profit', 'count'),
                pnl=('profit', 'sum'),
                win_rate=('profit', lambda x: (x > 0).mean() * 100)
            )
            print(grouped.to_string())
            
            print("\n--- By Close Reason ---")
            reason_grouped = df.groupby('reason').agg(
                trades=('profit', 'count'),
                pnl=('profit', 'sum')
            )
            print(reason_grouped.to_string())

        # 2. Today's trades (The opening today)
        print(f"\n--- Today's Opening Overview (Since {today_start.strftime('%Y-%m-%d %H:%M:%S UTC')}) ---")
        today_trades = [t for t in week_trades if t.opened_at >= today_start]
        print(f"Trades Opened Today: {len(today_trades)}")
        for t in today_trades:
            status_str = f"CLOSED ({t.close_reason}) PNL: ${t.profit:.2f}" if t.status == 'closed' else "OPEN"
            print(f"  {t.opened_at.strftime('%H:%M')} | {t.direction} {t.symbol} | Vol: {t.volume} | {status_str}")

        # 3. Check Account Drawdown
        snap_stmt = select(AccountSnapshot).where(AccountSnapshot.timestamp >= one_week_ago).order_by(asc(AccountSnapshot.timestamp))
        snap_result = await db.execute(snap_stmt)
        snapshots = snap_result.scalars().all()
        if snapshots:
            start_eq = snapshots[0].equity
            end_eq = snapshots[-1].equity
            min_eq = min([s.equity for s in snapshots])
            print(f"\n--- Equity Curve ---")
            print(f"Start Equity: ${start_eq:.2f}")
            print(f"End Equity:   ${end_eq:.2f}")
            print(f"Lowest Point: ${min_eq:.2f} (Max DD: {((start_eq - min_eq)/start_eq)*100:.1f}%)")

if __name__ == "__main__":
    asyncio.run(analyze())
