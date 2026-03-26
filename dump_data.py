
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import json

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        # Trades
        res = await conn.execute(text("SELECT * FROM trades"))
        trades = [dict(zip(res.keys(), r)) for r in res]
        
        # Decisions (last 20)
        res = await conn.execute(text("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT 20"))
        decisions = [dict(zip(res.keys(), r)) for r in res]
        
        # Account snapshots (last 10)
        res = await conn.execute(text("SELECT * FROM account_snapshots ORDER BY timestamp DESC LIMIT 10"))
        snapshots = [dict(zip(res.keys(), r)) for r in res]

        data = {
            "trades": trades,
            "decisions": decisions,
            "snapshots": snapshots
        }
        print(json.dumps(data, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
