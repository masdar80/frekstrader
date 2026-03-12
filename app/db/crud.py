"""
CRUD operations for database models.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Trade, Decision, Signal, AccountSnapshot, NewsEvent
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


async def get_trade_history(db: AsyncSession, limit: int = 50) -> List[Trade]:
    result = await db.execute(select(Trade).order_by(desc(Trade.opened_at)).limit(limit))
    return result.scalars().all()


async def close_trade(db: AsyncSession, trade_id: int, close_price: float, profit: float) -> Trade:
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if trade:
        trade.close_price = close_price
        trade.profit = profit
        trade.status = "closed"
        trade.closed_at = utcnow()
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
