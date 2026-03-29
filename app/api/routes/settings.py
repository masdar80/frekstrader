"""
Settings Routes — Configure Trading Mode dynamically.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import os
import dotenv

from app.config import settings, TradingMode
from app.db.database import get_db
from app.db import crud

router = APIRouter()

class ModeUpdate(BaseModel):
    mode: str
    use_ai_sentiment: bool = True

class HourConfig(BaseModel):
    day_of_week: int
    open_time: str
    close_time: str
    is_active: bool

class HoursUpdate(BaseModel):
    hours: List[HourConfig]

@router.put("/mode")
async def update_trading_mode(req: ModeUpdate):
    """Update trading mode via GUI slider."""
    try:
        new_mode = TradingMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid trading mode")
        
    # Update in memory
    settings.trading_mode = new_mode
    settings.use_ai_sentiment = req.use_ai_sentiment
    
    # Ideally save to .env to persist across restarts
    dotenv_file = dotenv.find_dotenv()
    if dotenv_file:
        dotenv.set_key(dotenv_file, "TRADING_MODE", new_mode.value)
        dotenv.set_key(dotenv_file, "USE_AI_SENTIMENT", "true" if req.use_ai_sentiment else "false")
        
    return {
        "success": True, 
        "mode": settings.trading_mode.value,
        "new_threshold": settings.confidence_threshold,
        "new_risk": settings.effective_max_risk_pct
    }

@router.get("/")
async def get_settings():
    return {
        "trading_mode": settings.trading_mode.value,
        "use_ai_sentiment": settings.use_ai_sentiment,
        "pairs": settings.pairs_list,
        "max_risk_pct": settings.max_risk_per_trade_pct,
        "daily_limit": settings.max_daily_loss_pct,
        "effective_risk": settings.effective_max_risk_pct,
        "threshold": settings.confidence_threshold
    }


@router.get("/hours")
async def get_trading_hours(db: AsyncSession = Depends(get_db)):
    """Fetch all trading hour configurations."""
    return await crud.get_trading_hours(db)


@router.put("/hours")
async def update_trading_hours(req: HoursUpdate, db: AsyncSession = Depends(get_db)):
    """Update trading hour configurations."""
    hours_data = [h.model_dump() for h in req.hours]
    await crud.update_trading_hours(db, hours_data)
    await db.commit()
    return {"success": True}
