import asyncio
import os
import sys
import json

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker

async def diagnose():
    print("--- 🔎 RAW HISTORY DIAGNOSTIC ---")
    connected = await broker.connect()
    if not connected:
        return

    # Try without params
    data = await broker._get("/history-deals") 
    print(f"Result for /history-deals (no params): {type(data)}")
    if isinstance(data, list):
        print(f"Total deals: {len(data)}")
        if data:
            print(f"Sample positionId: {data[0].get('positionId')}")
    else:
        print(f"Error or non-list response: {data}")

if __name__ == "__main__":
    asyncio.run(diagnose())
