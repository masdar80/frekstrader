import httpx
import asyncio
from app.config import settings
from app.utils.logger import logger

class AlertManager:
    """
    Handles sending critical production alerts (e.g., via Telegram).
    """
    def __init__(self):
        self.bot_token = getattr(settings, "telegram_bot_token", None)
        self.chat_id = getattr(settings, "telegram_chat_id", None)
        
    async def send_alert(self, message: str):
        logger.warning(f"ALERT: {message}")
        if not self.bot_token or not self.chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": f"🚨 ForeksTrader Alert 🚨\n\n{message}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

alert_manager = AlertManager()
