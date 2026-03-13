"""
Trading API Routes — Manual trade controls for the dashboard.
Requires API Key authentication.
"""
from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import Optional

from app.core.broker.metaapi_client import broker
from app.core.risk.manager import risk_manager
from app.config import settings

# API Key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not settings.app_api_key:
        # If no key is configured, reject all manual trades for safety
        raise HTTPException(status_code=403, detail="API Key not configured on server")
    if api_key != settings.app_api_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])

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
        
    # Check Risk Manager for manual trades too
    account_info = await broker.get_account_info()
    open_positions = await broker.get_positions()
    # We pass 0 for pnl since manual trades override daily limits, 
    # but still check max positions and margin.
    risk_check = risk_manager.check_trade_allowed(
        order.symbol, account_info, open_positions, 
        0, 0, account_info.get("equity", 0)
    )
    if not risk_check["allowed"]:
        raise HTTPException(status_code=400, detail=f"Risk blocked: {risk_check['reason']}")
        
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
