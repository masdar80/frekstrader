"""
Backtest Engine API stub.
"""
from fastapi import APIRouter

router = APIRouter()

from app.core.backtest.backtester import backtester
from pydantic import BaseModel

from typing import List
class BacktestRequest(BaseModel):
    symbols: List[str] = ["EURUSD"]
    days: int = 30

@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """Run a historical simulation on indicators-only strategy (Single or Portfolio)."""
    result = await backtester.run_portfolio(req.symbols, req.days)
    if result:
        return result.to_dict()
    return {"status": "error", "message": "Backtest failed to fetch data."}
