"""
Dashboard API Routes — Aggregate data for UI.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.db.database import get_db
from app.db import crud
from app.core.broker.metaapi_client import broker
from app.config import settings

router = APIRouter()

@router.get("/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """Fetch high-level overview."""
    if not broker.is_connected:
        return {"status": "offline", "error": "Broker not connected"}
        
    account_info = await broker.get_account_info(use_cache=True)
    open_positions = await broker.get_positions(use_cache=True)
    daily_pnl = await crud.get_daily_pnl(db)
    weekly_pnl = await crud.get_weekly_pnl(db)
    total_pnl = await crud.get_total_pnl(db)
    recent_decisions = await crud.get_recent_decisions(db, limit=10)
    
    decisions_list = []
    for d in recent_decisions:
        decisions_list.append({
            "id": d.id,
            "symbol": d.symbol,
            "action": d.action,
            "confidence": d.confidence,
            "reasoning": d.reasoning,
            "timestamp": d.timestamp,
            "trading_mode": d.trading_mode,
            "signals_json": d.signals_json
        })
    
    return {
        "status": "online",
        "trading_mode": settings.trading_mode.value,
        "account": account_info,
        "positions": open_positions,
        "metrics": {
            "daily_pnl": daily_pnl,
            "weekly_pnl": weekly_pnl,
            "total_pnl": total_pnl,
            "max_daily_loss": settings.max_daily_loss_pct,
            "risk_per_trade": settings.effective_max_risk_pct,
            "confidence_threshold": settings.confidence_threshold
        },
        "recent_decisions": decisions_list
    }

@router.get("/decisions")
async def get_decisions(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Audit log of recent brain decisions."""
    return await crud.get_recent_decisions(db, limit=limit)

@router.get("/equity-history")
async def get_equity_history_route(hours: int = 24, db: AsyncSession = Depends(get_db)):
    """Return account snapshots for equity curve chart."""
    snapshots = await crud.get_equity_history(db, hours)
    return [
        {
            "timestamp": s.timestamp,
            "equity": s.equity,
            "balance": s.balance,
            "drawdown_pct": s.drawdown_pct,
            "daily_pnl": s.daily_pnl
        }
        for s in snapshots
    ]

@router.get("/trade-history")
async def get_trade_history_route(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Return closed trades for history panel."""
    # We fetch a bit more than limit in case there are open trades, then filter
    trades = await crud.get_trade_history(db, limit=limit * 2)
    closed_trades = [
        {
            "id": t.id,
            "symbol": t.symbol,
            "direction": t.direction,
            "volume": t.volume,
            "open_price": t.open_price,
            "close_price": t.close_price,
            "profit": t.profit,
            "opened_at": t.opened_at,
            "closed_at": t.closed_at,
            "trading_mode": t.trading_mode
        }
        for t in trades if t.status == "closed"
    ]
    return closed_trades[:limit]

@router.get("/strategy-stats")
async def get_strategy_stats(db: AsyncSession = Depends(get_db)):
    """Return win rate, profit factor, avg win/loss per trading mode."""
    # Query closed trades
    result = await db.execute(
        select(crud.Trade).where(crud.Trade.status == "closed")
    )
    trades = result.scalars().all()
    
    stats = {}
    for t in trades:
        mode = t.trading_mode or "unknown"
        if mode not in stats:
            stats[mode] = {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
            }
        
        stats[mode]["total_trades"] += 1
        if t.profit and t.profit > 0:
            stats[mode]["winning_trades"] += 1
            stats[mode]["gross_profit"] += t.profit
        else:
            stats[mode]["losing_trades"] += 1
            stats[mode]["gross_loss"] += abs(t.profit or 0.0)
            
    # Calculate derived metrics
    for mode, data in stats.items():
        data["win_rate"] = data["winning_trades"] / data["total_trades"] if data["total_trades"] > 0 else 0
        data["profit_factor"] = data["gross_profit"] / data["gross_loss"] if data["gross_loss"] > 0 else (999.9 if data["gross_profit"] > 0 else 0.0)
        data["avg_win"] = data["gross_profit"] / data["winning_trades"] if data["winning_trades"] > 0 else 0
        data["avg_loss"] = data["gross_loss"] / data["losing_trades"] if data["losing_trades"] > 0 else 0
        data["net_profit"] = data["gross_profit"] - data["gross_loss"]
        
    return stats
