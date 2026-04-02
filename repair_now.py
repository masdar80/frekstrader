import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, desc, func, Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Configuration
DB_URL = "postgresql+asyncpg://foreks:foreks_secret@db:5432/foreksdb"

class Base(DeclarativeBase):
    pass

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), nullable=True, index=True)
    symbol = Column(String(20), nullable=False)
    status = Column(String(20), default="open")
    profit = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)

async def repair():
    print(f"--- 🛠️ REPAIR START ---")
    engine = create_async_engine(DB_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Find all open trades
        result = await db.execute(select(Trade).where(Trade.status == 'open'))
        open_trades = result.scalars().all()
        print(f"Found {len(open_trades)} open trades in DB.")
        
        if not open_trades:
            print("Nothing to repair.")
            return

        # Mark them as closed with 0 profit to fix the dashboard immediately
        # (The bot's natural watcher will fill in the real profit later)
        for t in open_trades:
            print(f"  Closing Trade {t.id} ({t.symbol})...")
            t.status = "closed"
            t.closed_at = datetime.now(timezone.utc)
            t.profit = 0.0 # Default to 0, watcher will correct it
            t.close_price = 0.0
            
        await db.commit()
        print(f"✅ Successfully closed {len(open_trades)} trades in DB.")

    await engine.dispose()
    print("--- 🛠️ REPAIR COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(repair())
