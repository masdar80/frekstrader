import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, text
from app.db.database import async_session
from app.db.models import Trade, AccountSnapshot

async def check_last_week():
    async with async_session() as db:
        # Get timestamp for 7 days ago
        last_week = datetime.utcnow() - timedelta(days=7)
        
        print(f"--- Performance Since {last_week.strftime('%Y-%m-%d %H:%M:%S')} UTC ---")
        
        # 1. Trades summary
        stmt = select(
            func.count(Trade.id).label("total_trades"),
            func.sum(Trade.profit).label("total_profit"),
            func.count(Trade.id).filter(Trade.profit > 0).label("winning_trades"),
            func.count(Trade.id).filter(Trade.profit < 0).label("losing_trades"),
            func.max(Trade.profit).label("biggest_win"),
            func.min(Trade.profit).label("biggest_loss")
        ).where(Trade.status == "closed", Trade.closed_at >= last_week)
        
        result = await db.execute(stmt)
        row = result.first()
        
        if row and row.total_trades > 0:
            total_trades = row.total_trades
            win_rate = (row.winning_trades / total_trades) * 100 if total_trades > 0 else 0
            print(f"Total Trades Closed: {total_trades}")
            print(f"Total Profit/Loss: ${row.total_profit:.2f}")
            print(f"Win Rate: {win_rate:.1f}% ({row.winning_trades}W / {row.losing_trades}L)")
            print(f"Biggest Win: ${row.biggest_win:.2f}")
            print(f"Biggest Loss: ${row.biggest_loss:.2f}")
        else:
            print("No trades closed in the last 7 days.")
            
        print("\n--- Open Trades ---")
        open_stmt = select(func.count(Trade.id)).where(Trade.status == "open")
        open_result = await db.execute(open_stmt)
        print(f"Currently Open Positions: {open_result.scalar()}")

        # 2. Account growth
        # Get oldest snapshot from last 7 days
        snap_stmt_old = select(AccountSnapshot).where(AccountSnapshot.timestamp >= last_week).order_by(AccountSnapshot.timestamp.asc()).limit(1)
        old_snap = (await db.execute(snap_stmt_old)).scalar_one_or_none()
        
        # Get latest snapshot
        snap_stmt_new = select(AccountSnapshot).order_by(AccountSnapshot.timestamp.desc()).limit(1)
        new_snap = (await db.execute(snap_stmt_new)).scalar_one_or_none()
        
        if old_snap and new_snap:
            print("\n--- Account Growth ---")
            print(f"Equity 7 days ago: ${old_snap.equity:.2f}")
            print(f"Equity Now:        ${new_snap.equity:.2f}")
            diff = new_snap.equity - old_snap.equity
            pct = (diff / old_snap.equity) * 100 if old_snap.equity > 0 else 0
            print(f"Growth:            ${diff:.2f} ({pct:.2f}%)")
            print(f"Max Drawdown Rec:  {new_snap.drawdown_pct:.2f}%")
        else:
            print("\nNot enough snapshot data to calculate account growth.")
            
if __name__ == "__main__":
    asyncio.run(check_last_week())
