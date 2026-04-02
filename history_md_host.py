import asyncio
import os
import sys
import httpx
import json

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker
from app.config import settings

async def diagnose():
    print("--- 🔎 MARKET DATA HOST HISTORY DIAGNOSTIC ---")
    connected = await broker.connect()
    if not connected:
        return

    client = httpx.AsyncClient(headers=broker._headers)
    
    # Try calling on the market data host (no -b region)
    region = "london" # from connect() logs
    md_base = f"https://mt-market-data-client-api-v1.{region}.agiliumtrade.ai"
    url = f"{md_base}/users/current/accounts/{settings.metaapi_account_id}/history-deals"
    
    print(f"Testing {url}...")
    resp = await client.get(url)
    print(f"  {resp.status_code}: {resp.text[:200]}")
    
    if resp.status_code == 200:
        print("✅ SUCCESS! History is on the MT Market Data host.")

    await client.aclose()

if __name__ == "__main__":
    asyncio.run(diagnose())
