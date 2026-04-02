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
    max_risk_amount_usd: float = 20.0
    trailing_stop_enabled: bool = True
    allow_multiple_per_pair: bool = False
    max_open_positions: int = 15
    pairs: List[str] = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]

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
    settings.max_risk_amount_usd = req.max_risk_amount_usd
    settings.trailing_stop_enabled = req.trailing_stop_enabled
    settings.allow_multiple_per_pair = req.allow_multiple_per_pair
    settings.max_open_positions = req.max_open_positions
    settings.trading_pairs = ",".join([p.upper() for p in req.pairs])
    
    # Ideally save to .env to persist across restarts
    dotenv_file = dotenv.find_dotenv()
    if dotenv_file:
        dotenv.set_key(dotenv_file, "TRADING_MODE", new_mode.value)
        dotenv.set_key(dotenv_file, "USE_AI_SENTIMENT", "true" if req.use_ai_sentiment else "false")
        dotenv.set_key(dotenv_file, "MAX_RISK_AMOUNT_USD", str(req.max_risk_amount_usd))
        dotenv.set_key(dotenv_file, "TRAILING_STOP_ENABLED", "true" if req.trailing_stop_enabled else "false")
        dotenv.set_key(dotenv_file, "ALLOW_MULTIPLE_PER_PAIR", "true" if req.allow_multiple_per_pair else "false")
        dotenv.set_key(dotenv_file, "MAX_OPEN_POSITIONS", str(req.max_open_positions))
        dotenv.set_key(dotenv_file, "TRADING_PAIRS", settings.trading_pairs)
        
    return {
        "success": True, 
        "mode": settings.trading_mode.value,
        "new_threshold": settings.confidence_threshold,
        "new_risk": settings.effective_max_risk_pct,
        "max_risk_amount_usd": settings.max_risk_amount_usd,
        "trailing_stop_enabled": settings.trailing_stop_enabled,
        "pairs": settings.pairs_list
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
        "threshold": settings.confidence_threshold,
        "max_risk_amount_usd": settings.max_risk_amount_usd,
        "trailing_stop_enabled": settings.trailing_stop_enabled,
        "allow_multiple_per_pair": settings.allow_multiple_per_pair,
        "max_open_positions": settings.max_open_positions
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
