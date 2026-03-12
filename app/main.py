"""
ForeksTrader — Main FastAPI Application
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import engine, Base
from app.api.routes import trading, analysis, dashboard, backtest, settings as settings_routes
from app.api.websocket import router as ws_router, broadcast_market_data
from app.workers.market_watcher import watcher
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 ForeksTrader starting up...")
    logger.info(f"   Trading Mode: {settings.trading_mode.value}")
    logger.info(f"   Pairs: {settings.pairs_list}")
    logger.info(f"   Confidence Threshold: {settings.confidence_threshold}")
    logger.info(f"   Max Risk/Trade: {settings.effective_max_risk_pct}%")

    # Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start Background Workers
    app.state.watcher_task = asyncio.create_task(watcher.start())
    app.state.ws_task = asyncio.create_task(broadcast_market_data())

    logger.info("✅ ForeksTrader ready!")
    yield
    
    logger.info("🛑 ForeksTrader shutting down...")
    await watcher.stop()
    if hasattr(app.state, 'watcher_task'):
        app.state.watcher_task.cancel()
    if hasattr(app.state, 'ws_task'):
        app.state.ws_task.cancel()

app = FastAPI(
    title="ForeksTrader",
    description="AI-Powered Forex Trading System with Skeptical Decision Making",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === API Routes ===
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["Settings"])
app.include_router(ws_router, tags=["WebSocket"])

# === Static Files (Frontend) ===
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the main dashboard."""
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "ForeksTrader API is running. Frontend not found."}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "trading_mode": settings.trading_mode.value,
        "pairs": settings.pairs_list,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.debug)
