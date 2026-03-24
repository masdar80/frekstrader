"""
Analysis & Signals Routes.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict

from app.db.database import get_db
from app.db import crud
from app.core.broker.metaapi_client import broker

router = APIRouter()

@router.get("/signals/{symbol}")
async def get_symbol_signals(symbol: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get latest generated analysis signals for a pair."""
    return await crud.get_latest_signals(db, symbol, limit=limit)

@router.get("/news")
async def get_recent_news(hours: int = 24, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent fetched news articles and AI sentiment."""
    return await crud.get_recent_news(db, hours=hours, limit=limit)

@router.get("/chart/{symbol}")
async def get_chart_data(symbol: str, timeframe: str = "15m", limit: int = 200):
    """Get chart candles for the frontend."""
    candles = await broker.get_candles(symbol, timeframe=timeframe, count=limit)
    return {"symbol": symbol, "timeframe": timeframe, "candles": candles}

@router.get("/sentiment/{symbol}")
async def get_symbol_sentiment(symbol: str):
    """Get the latest cached sentiment for a symbol."""
    from app.workers.market_watcher import watcher
    return watcher._sentiment_cache.get(symbol, {
        "symbol": symbol, "signal": "NEUTRAL", "score": 0.0,
        "strength": 0.0, "confidence": 0.0,
        "reasoning": "Loading..."
    })

