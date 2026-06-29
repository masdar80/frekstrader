import asyncio
from app.config import settings
from app.core.broker.metaapi_client import broker
from app.workers.market_watcher import MarketWatcher

async def test():
    await broker.connect()
    pos = await broker.get_positions()
    print(f"Got {len(pos)} positions from broker")
    watcher = MarketWatcher()
    print(f"Max Trade Hours in settings: {settings.max_trade_hours}")
    await watcher._check_trade_timeouts(pos)
    print("Done checking timeouts")

asyncio.run(test())
