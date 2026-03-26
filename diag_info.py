
import asyncio
from app.core.broker.metaapi_client import broker

async def diag_info():
    await broker.connect()
    info = await broker.get_account_info()
    print("ACCOUNT INFO:", info)
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(diag_info())
