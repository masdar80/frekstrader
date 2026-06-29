import asyncio
import json
from app.core.broker.metaapi_client import broker

async def test():
    await broker.connect()
    pos = await broker.get_positions()
    print(json.dumps(pos, indent=2))

asyncio.run(test())
