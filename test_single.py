import asyncio
from app.core.broker.metaapi_client import broker

async def test():
    print("Connecting...")
    success = await broker.connect()
    print(f"Connected: {success}")
    if success:
        print("Fetching account info...")
        info = await broker.get_account_info()
        print(f"Info: {info}")
        
        print("Fetching positions...")
        pos = await broker.get_positions()
        print(f"Positions: {pos}")
        
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
