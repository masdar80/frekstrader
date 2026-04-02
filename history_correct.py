import asyncio
import os
import sys
import json
from datetime import datetime, timezone, timedelta

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker

async def diagnose():
    print("--- 🔎 CORRECTED HISTORY DIAGNOSTIC ---")
    connected = await broker.connect()
    if not connected:
        return

    # Try WITH /history/deals
    start = datetime.now(timezone.utc) - timedelta(days=7)
    start_str = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    data = await broker._get("/history/deals", params={"startTime": start_str, "endTime": end_str})
    
    if data is None:
        print("❌ /history/deals still returned None!")
    elif isinstance(data, list):
        print(f"✅ /history/deals returned {len(data)} deals!")
        if data:
            print("Sample deal structure:")
            print(json.dumps(data[0], indent=2))
    else:
        print(f"Unexpected response type: {type(data)}")
        print(data)

if __name__ == "__main__":
    asyncio.run(diagnose())
