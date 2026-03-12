"""
Backtest Engine API stub.
"""
from fastapi import APIRouter

router = APIRouter()

@router.post("/run")
async def run_backtest():
    """Placeholder for Phase 7 implementation."""
    return {"status": "pending", "message": "Backtesting engine in development."}
