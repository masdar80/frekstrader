import asyncio
import os
import sys
import httpx

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker

async def diagnose():
    print("--- 🔎 FINAL SEARCH FOR HISTORY ENDPOINT ---")
    connected = await broker.connect()
    if not connected:
        return

    client = httpx.AsyncClient(headers=broker._headers)
    
    # Try the most common combinations
    possible_paths = [
        "/history-deals",
        "/history/deals",
        "/deals",
        "/history",
        "/historical-trades"
    ]
    
    for p in possible_paths:
        url = f"{broker._account_url}{p}"
        resp = await client.get(url)
        print(f"PATH {p} -> {resp.status_code}")
        if resp.status_code == 200:
            print(f"  FOUND IT! {len(resp.json())} items.")
            return

    await client.aclose()

if __name__ == "__main__":
    asyncio.run(diagnose())
