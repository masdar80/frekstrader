"""
ForeksTrader — Main FastAPI Application
"""
import os
import secrets
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from app.config import settings
from app.db.database import engine, Base
from app.api.routes import trading, analysis, dashboard, backtest, settings as settings_routes, emergency
from app.api.websocket import router as ws_router, broadcast_market_data
from app.workers.market_watcher import watcher
from app.core.broker.metaapi_client import broker
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 ForeksTrader starting up...")
    logger.info(f"   Trading Mode: {settings.trading_mode.value}")
    logger.info(f"   Pairs: {settings.pairs_list}")
    logger.info(f"   Confidence Threshold: {settings.confidence_threshold}")
    logger.info(f"   Max Risk/Trade: {settings.effective_max_risk_pct}%")

    # Generate API Key if not set
    if not settings.app_api_key:
        new_key = secrets.token_urlsafe(32)
        logger.warning(f"🔑 No API Key found. Generated new key: {new_key}")
        logger.warning("   (Please save this to your .env file as APP_API_KEY)")
        settings.app_api_key = new_key
        # Try to append to .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        try:
            with open(env_path, "a") as f:
                f.write(f"\n# Auto-generated API Key for manual trading\nAPP_API_KEY={new_key}\n")
            logger.info("   Saved new API key to .env file")
        except Exception as e:
            logger.error(f"   Failed to save API key to .env: {e}")

    # 1. Database Health Check
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("   DB Connection: OK")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        # In production, we might want to exit here
    
    # 2. Broker Connection Check
    try:
        if not broker.is_connected:
            success = await broker.connect()
            if success:
                logger.info("   Broker Connection: OK")
            else:
                logger.error("❌ Broker connection failed on startup")
    except Exception as e:
        logger.error(f"❌ Broker initialization error: {e}")

    # 3. Create DB tables
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

# CORS middleware
origins = [o.strip() for o in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*", "X-API-Key"],
)

# === API Routes ===
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["Settings"])
app.include_router(emergency.router, prefix="/api/emergency", tags=["Emergency"])
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
