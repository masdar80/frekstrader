import asyncio
from app.core.broker.metaapi_client import broker

async def close_all():
    await broker.connect()
    pos = await broker.get_positions()
    print(f"Found {len(pos)} open positions at broker. Closing all...")
    for p in pos:
        pid = p.get('id')
        print(f"Closing {pid}...")
        await broker.close_position(pid)
    print("Done closing positions at broker.")

asyncio.run(close_all())
