
import asyncio
from app.core.broker.metaapi_client import broker

async def debug_history():
    await broker.connect()
    deals = await broker.get_history(days=2)
    print(f"Total deals found: {len(deals)}")
    for d in deals[:10]:
        print(d)
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_history())
