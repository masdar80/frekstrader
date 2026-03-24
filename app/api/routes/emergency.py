from fastapi import APIRouter, Depends, HTTPException, Header
from app.config import settings
from app.workers.market_watcher import watcher

router = APIRouter()

async def verify_api_key(x_api_key: str = Header(None)):
    """Dependency to check the API key."""
    if not settings.app_api_key:
        return True
    if x_api_key != settings.app_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

@router.post("/pause", dependencies=[Depends(verify_api_key)])
async def pause_trading():
    watcher.pause()
    return {"success": True, "message": "Trading paused"}

@router.post("/resume", dependencies=[Depends(verify_api_key)])
async def resume_trading():
    watcher.resume()
    return {"success": True, "message": "Trading resumed"}

@router.post("/close-all", dependencies=[Depends(verify_api_key)])
async def emergency_close_all():
    await watcher.emergency_close_all()
    return {"success": True, "message": "Emergency close triggered and trading paused."}

@router.get("/status")
async def get_emergency_status():
    return {
        "is_running": watcher.is_running,
        "is_paused": watcher.is_paused
    }
