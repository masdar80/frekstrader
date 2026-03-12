"""
WebSocket Manager for real-time frontend updates.
"""
import json
import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.utils.logger import logger
from app.core.broker.metaapi_client import broker

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected to WebSocket. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

    async def broadcast_decision(self, decision: dict):
        payload = {
            "type": "decision_update",
            "data": decision
        }
        await self.broadcast(json.dumps(payload))

manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle client requests if needed
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        
        
async def broadcast_market_data():
    """Background task to push live account/position updates."""
    while True:
        try:
            if broker.is_connected and manager.active_connections:
                info = await broker.get_account_info(use_cache=True)
                positions = await broker.get_positions(use_cache=True)
                
                payload = {
                    "type": "account_update",
                    "data": {
                        "account": info,
                        "positions": positions
                    }
                }
                await manager.broadcast(json.dumps(payload))
        except Exception as e:
            logger.error(f"WS broadcast error: {e}")
            
        await asyncio.sleep(5)  # Update every 5 seconds
