import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker

async def test():
    print("--- 🔎 TESTING TIME-BASED HISTORY ENDPOINT ---")
    connected = await broker.connect()
    if not connected:
        return

    # Try WITH /history-deals/time/:startTime/:endTime
    start = datetime.now(timezone.utc) - timedelta(days=7)
    start_str = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # The endpoint is /history-deals/time/:startTime/:endTime
    # In MetaAPIClient: self._account_url + path
    path = f"/history-deals/time/{start_str}/{end_str}"
    print(f"Calling: {broker._account_url}{path}")
    
    data = await broker._get(path)
    
    if data is None:
        print("❌ /history-deals/time/... returned None!")
    elif isinstance(data, list):
        print(f"✅ /history-deals/time/... returned {len(data)} deals!")
        if data:
            print("Sample deal:")
            import json
            print(json.dumps(data[0], indent=2))
    else:
        print(f"Unexpected response type: {type(data)}")
        print(data)

if __name__ == "__main__":
    asyncio.run(test())
