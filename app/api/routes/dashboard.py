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
    recent_decisions = await crud.get_recent_decisions(db, limit=10)
    
    return {
        "status": "online",
        "trading_mode": settings.trading_mode.value,
        "account": account_info,
        "positions": open_positions,
        "metrics": {
            "daily_pnl": daily_pnl,
            "weekly_pnl": weekly_pnl,
            "max_daily_loss": settings.max_daily_loss_pct,
            "risk_per_trade": settings.effective_max_risk_pct,
            "confidence_threshold": settings.confidence_threshold
        },
        "recent_decisions": recent_decisions
    }

@router.get("/decisions")
async def get_decisions(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Audit log of recent brain decisions."""
    return await crud.get_recent_decisions(db, limit=limit)
