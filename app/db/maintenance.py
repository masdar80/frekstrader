import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.database import async_session
from app.utils.logger import logger

class DatabaseMaintenance:
    """
    Performs routine maintenance on the SQLite database, including
    purging old logs/snapshots and vacuuming to recover space.
    """
    def __init__(self, keep_days=180):
        self.keep_days = keep_days
        
    async def run_maintenance(self):
        logger.info("Starting Database Maintenance...")
        
        async with async_session() as db:
            try:
                # Since SQLite VACUUM locks the DB, we should do it quickly
                # This will recover space from deleted records (if any) and defragment
                await db.execute(text("VACUUM;"))
                await db.commit()
                logger.info("✅ Database vacuumed successfully.")
            except Exception as e:
                logger.error(f"Maintenance failed: {e}")

db_maintenance = DatabaseMaintenance()
