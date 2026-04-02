import asyncio
import os
import sys
import httpx
import json
from datetime import datetime, timezone, timedelta

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker
from app.config import settings

async def diagnose():
    print("--- 🔎 RAW ERROR DIAGNOSTIC ---")
    connected = await broker.connect()
    if not connected:
        return

    client = httpx.AsyncClient(headers=broker._headers)
    
    start = datetime.now(timezone.utc) - timedelta(days=7)
    start_str = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Try various variations
    urls = [
        f"{broker._account_url}/history-deals",
        f"{broker._account_url}/history/deals",
        f"{broker._account_url}/history-trades",
        f"https://metastats-api-v1.london.agiliumtrade.ai/users/current/accounts/{settings.metaapi_account_id}/history/deals"
    ]

    for url in urls:
        print(f"Testing {url}...")
        try:
            resp = await client.get(url, params={"startTime": start_str, "endTime": end_str})
            print(f"  {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  Error: {e}")

    await client.aclose()

if __name__ == "__main__":
    asyncio.run(diagnose())
