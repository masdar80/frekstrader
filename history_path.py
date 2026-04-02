import asyncio
import os
import sys
import json
from datetime import datetime, timezone, timedelta

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker

async def diagnose():
    print("--- 🔎 PATH-BASED HISTORY DIAGNOSTIC ---")
    connected = await broker.connect()
    if not connected:
        return

    # Try Path-based startTime/endTime
    start = datetime.now(timezone.utc) - timedelta(days=7)
    start_str = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # This bypasses broker._get to try raw path
    path = f"/history/deals/startTime/{start_str}/endTime/{end_str}"
    print(f"Trying path: {path}")
    data = await broker._get(path)
    
    if data is None:
        print("❌ Path-based history returned None!")
    elif isinstance(data, list):
        print(f"✅ Path-based history returned {len(data)} deals!")
    else:
        print(f"Unexpected response: {data}")

if __name__ == "__main__":
    asyncio.run(diagnose())
