import asyncio
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker

async def inspect():
    await broker.connect()
    deals = await broker.get_deals_by_position("56591861238")
    print("Deals for 56591861238:")
    import json
    print(json.dumps(deals, indent=2))
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(inspect())
