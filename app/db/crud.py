"""
CRUD operations for database models.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Trade, Decision, Signal, AccountSnapshot, NewsEvent, TradingHours
from app.utils.helpers import utcnow


# === Trades ===

async def create_trade(db: AsyncSession, **kwargs) -> Trade:
    trade = Trade(**kwargs)
    db.add(trade)
    await db.flush()
    return trade


async def get_open_trades(db: AsyncSession) -> List[Trade]:
    result = await db.execute(select(Trade).where(Trade.status == "open").order_by(desc(Trade.opened_at)))
    return result.scalars().all()


async def get_open_trades_by_external_id(db: AsyncSession) -> Dict[str, Trade]:
    """Returns a dict mapping external_id to open Trade objects."""
    result = await db.execute(select(Trade).where(Trade.status == "open", Trade.external_id.isnot(None)))
    trades = result.scalars().all()
    return {t.external_id: t for t in trades}


async def get_trade_history(db: AsyncSession, limit: int = 10, offset: int = 0) -> List[Trade]:
    result = await db.execute(
        select(Trade)
        .where(Trade.status == "closed")
        .order_by(desc(Trade.closed_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def close_trade(db: AsyncSession, trade_id: int, close_price: float, profit: float, close_reason: Optional[str] = None) -> Trade:
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if trade:
        trade.close_price = close_price
        trade.profit = profit
        trade.status = "closed"
        trade.closed_at = utcnow()
        if close_reason:
            trade.close_reason = close_reason
    return trade


async def update_trade_metadata(db: AsyncSession, trade_id: int, metadata: Dict[str, Any]) -> Optional[Trade]:
    """Update the metadata_json field of a trade."""
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if trade:
        trade.metadata_json = metadata
    return trade


# === Decisions ===

async def create_decision(db: AsyncSession, **kwargs) -> Decision:
    decision = Decision(**kwargs)
    db.add(decision)
    await db.flush()
    return decision


async def get_recent_decisions(db: AsyncSession, limit: int = 50) -> List[Decision]:
    result = await db.execute(select(Decision).order_by(desc(Decision.timestamp)).limit(limit))
    return result.scalars().all()


async def update_decision_outcome(db: AsyncSession, trade_id: int, was_profitable: bool):
    """Update was_profitable field on all decisions linked to a trade."""
    result = await db.execute(select(Decision).where(Decision.trade_id == trade_id))
    decisions = result.scalars().all()
    for dec in decisions:
        dec.was_profitable = was_profitable


# === Signals ===

async def create_signal(db: AsyncSession, **kwargs) -> Signal:
    signal = Signal(**kwargs)
    db.add(signal)
    await db.flush()
    return signal


async def get_latest_signals(db: AsyncSession, symbol: str, limit: int = 20) -> List[Signal]:
    result = await db.execute(
        select(Signal).where(Signal.symbol == symbol).order_by(desc(Signal.timestamp)).limit(limit)
    )
    return result.scalars().all()


# === Account Snapshots ===

async def create_snapshot(db: AsyncSession, **kwargs) -> AccountSnapshot:
    snapshot = AccountSnapshot(**kwargs)
    db.add(snapshot)
    await db.flush()
    return snapshot


async def get_latest_snapshot(db: AsyncSession) -> Optional[AccountSnapshot]:
    result = await db.execute(select(AccountSnapshot).order_by(desc(AccountSnapshot.timestamp)).limit(1))
    return result.scalar_one_or_none()


async def get_equity_history(db: AsyncSession, hours: int = 24) -> List[AccountSnapshot]:
    cutoff = utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(AccountSnapshot)
        .where(AccountSnapshot.timestamp >= cutoff)
        .order_by(AccountSnapshot.timestamp.asc())
    )
    return result.scalars().all()


async def get_daily_pnl(db: AsyncSession) -> float:
    """Get total P&L for today from closed trades."""
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.sum(Trade.profit)).where(
            Trade.status == "closed",
            Trade.closed_at >= today_start
        )
    )
    return result.scalar() or 0.0


async def get_weekly_pnl(db: AsyncSession) -> float:
    """Get total P&L for this week."""
    now = utcnow()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.sum(Trade.profit)).where(
            Trade.status == "closed",
            Trade.closed_at >= week_start
        )
    )
    return result.scalar() or 0.0


async def get_total_pnl(db: AsyncSession) -> float:
    """Get total P&L for all time from closed trades."""
    result = await db.execute(
        select(func.sum(Trade.profit)).where(
            Trade.status == "closed"
        )
    )
    return result.scalar() or 0.0


# === News ===

async def create_news_event(db: AsyncSession, **kwargs) -> NewsEvent:
    event = NewsEvent(**kwargs)
    db.add(event)
    await db.flush()
    return event


async def get_recent_news(db: AsyncSession, hours: int = 24, limit: int = 20) -> List[NewsEvent]:
    cutoff = utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(NewsEvent).where(NewsEvent.timestamp >= cutoff).order_by(desc(NewsEvent.timestamp)).limit(limit)
    )
    return result.scalars().all()


# === Trading Hours ===

async def get_trading_hours(db: AsyncSession) -> List[TradingHours]:
    """Get all trading hours config (sorted by day)."""
    result = await db.execute(select(TradingHours).order_by(TradingHours.day_of_week.asc()))
    return result.scalars().all()


async def update_trading_hours(db: AsyncSession, hours_list: List[Dict[str, Any]]):
    """Bulk update or create trading hours."""
    for h in hours_list:
        day = h.get("day_of_week")
        result = await db.execute(select(TradingHours).where(TradingHours.day_of_week == day))
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.open_time = h.get("open_time", "00:00")
            existing.close_time = h.get("close_time", "23:59")
            existing.is_active = h.get("is_active", True)
        else:
            new_h = TradingHours(
                day_of_week=day,
                open_time=h.get("open_time", "00:00"),
                close_time=h.get("close_time", "23:59"),
                is_active=h.get("is_active", True)
            )
            db.add(new_h)
    await db.flush()


async def is_market_open(db: AsyncSession) -> bool:
    """Check if current time is within active trading hours (using UTC)."""
    now = utcnow()
    day = now.weekday()  # 0=Monday
    time_str = now.strftime("%H:%M")
    
    result = await db.execute(
        select(TradingHours).where(TradingHours.day_of_week == day)
    )
    hour_conf = result.scalar_one_or_none()
    
    if not hour_conf:
        # Default to open if no configuration exists for this day yet
        return True
        
    if not hour_conf.is_active:
        return False
        
    return hour_conf.open_time <= time_str <= hour_conf.close_time


async def get_performance_metrics(db: AsyncSession) -> Dict[str, Any]:
    """Calculate Win Rate and Sharpe Ratio from history."""
    # 1. Win Rate
    res_trades = await db.execute(select(Trade).where(Trade.status == "closed"))
    closed_trades = res_trades.scalars().all()
    
    total = len(closed_trades)
    wins = len([t for t in closed_trades if (t.profit or 0) > 0])
    win_rate = (wins / total) if total > 0 else 0.0

    # 2. Sharpe Ratio (Simplified)
    # Annualized Sharpe = sqrt(252) * [mean(daily_returns) / std(daily_returns)]
    # We fetch equity snapshots and group by day
    res_snaps = await db.execute(
        select(AccountSnapshot).order_by(AccountSnapshot.timestamp.asc())
    )
    all_snaps = res_snaps.scalars().all()
    
    # Filter to one snapshot per day (last one of the day)
    daily_equities = {}
    for s in all_snaps:
        date_str = s.timestamp.date().isoformat()
        daily_equities[date_str] = s.equity
        
    equity_list = list(daily_equities.values())
    
    sharpe_ratio = 0.0
    if len(equity_list) >= 3: # Need at least 3 days for a standard deviation
        import numpy as np
        # Calculate daily % returns
        returns = []
        for i in range(1, len(equity_list)):
            prev = equity_list[i-1]
            curr = equity_list[i]
            if prev > 0:
                returns.append((curr - prev) / prev)
        
        if returns and np.std(returns) > 0:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            # 252 trading days in a year
            sharpe_ratio = (avg_return / std_return) * np.sqrt(252)
            
    return {
        "win_rate": round(win_rate * 100, 2),
        "total_trades": total,
        "sharpe_ratio": round(sharpe_ratio, 3)
    }


async def purge_all_trading_data(db: AsyncSession):
    """Purge all trading-related data for a fresh start."""
    from sqlalchemy import delete
    await db.execute(delete(Signal))
    await db.execute(delete(Decision))
    await db.execute(delete(AccountSnapshot))
    await db.execute(delete(Trade))
    await db.flush()
