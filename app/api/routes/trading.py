"""
Trading API Routes — Manual trade controls for the dashboard.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.broker.metaapi_client import broker

router = APIRouter()

class OrderRequest(BaseModel):
    symbol: str
    direction: str  # BUY or SELL
    volume: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

@router.post("/execute")
async def execute_trade(order: OrderRequest):
    """Manually execute a trade."""
    if not broker.is_connected:
        raise HTTPException(status_code=503, detail="Broker not connected")
        
    res = await broker.place_order(
        order.symbol, order.direction, order.volume, 
        stop_loss=order.stop_loss, take_profit=order.take_profit,
        comment="Manual_Dashboard"
    )
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/close/{position_id}")
async def close_trade(position_id: str):
    """Manually close an open position."""
    if not broker.is_connected:
        raise HTTPException(status_code=503, detail="Broker not connected")
        
    res = await broker.close_position(position_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/positions")
async def get_open_positions():
    """Get all currently open positions."""
    if not broker.is_connected:
        raise HTTPException(status_code=503, detail="Broker not connected")
    return await broker.get_positions()
