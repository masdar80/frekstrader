
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import json

DATABASE_URL = "sqlite+aiosqlite:////app/foreks.db"

async def main():
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            # Query all trades and their linked decisions
            query = """
                SELECT t.id, t.symbol, t.direction, t.status, t.profit, t.opened_at, t.closed_at, d.reasoning, d.confidence
                FROM trades t
                LEFT JOIN decisions d ON t.id = d.trade_id
                ORDER BY t.id ASC
            """
            res = await conn.execute(text(query))
            trades = [dict(zip(res.keys(), r)) for r in res]
            
            # Query recent rejections
            query_rejections = "SELECT symbol, action, timestamp, reasoning FROM decisions WHERE action='REJECT' ORDER BY timestamp DESC LIMIT 5"
            res_rej = await conn.execute(text(query_rejections))
            rejections = [dict(zip(res_rej.keys(), r)) for r in res_rej]
            
            # Query account history (last 10)
            query_acc = "SELECT timestamp, balance, equity, drawdown_pct FROM account_snapshots ORDER BY timestamp DESC LIMIT 10"
            res_acc = await conn.execute(text(query_acc))
            snapshots = [dict(zip(res_acc.keys(), r)) for r in res_acc]

            print(json.dumps({
                "trades_with_decisions": trades,
                "recent_rejections": rejections,
                "recent_snapshots": snapshots
            }, indent=2, default=str))

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
