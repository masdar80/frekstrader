import asyncio
import os
import sys
import httpx

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker

async def diagnose():
    print("--- 🔎 POSITION-BASED HISTORY DIAGNOSTIC ---")
    connected = await broker.connect()
    if not connected:
        return

    client = httpx.AsyncClient(headers=broker._headers)
    
    # Try getting deals for one of the orphaned position IDs
    pid = "56011396572" # AUDUSD pos
    url = f"{broker._account_url}/history-deals/position/{pid}"
    
    print(f"Testing {url}...")
    resp = await client.get(url)
    print(f"  {resp.status_code}: {resp.text[:200]}")

    await client.aclose()

if __name__ == "__main__":
    asyncio.run(diagnose())
