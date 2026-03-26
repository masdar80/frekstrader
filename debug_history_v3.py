
import asyncio
import os
from datetime import datetime, timedelta, timezone
import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID")
HEADERS = {"auth-token": TOKEN, "Content-Type": "application/json"}

async def debug_position_history(position_id):
    # Discovery
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}",
            headers=HEADERS
        )
        region = resp.json().get("region", "london")
        base_url = f"https://mt-client-api-v1.{region}-b.agiliumtrade.ai"
        
        # History
        start = datetime.now(timezone.utc) - timedelta(days=3)
        # Use simpler format without microseconds and +00:00 if needed, but lets try default first
        params = {
            "startTime": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
        
        print(f"Fetching history from {base_url}...")
        url = f"{base_url}/users/current/accounts/{ACCOUNT_ID}/history-deals/time"
        resp = await client.get(url, params=params, headers=HEADERS)
        
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}")
            return

        deals = resp.json()
        print(f"Found {len(deals)} deals in last 3 days.")
        
        target_deals = [d for d in deals if d.get("positionId") == position_id]
        print(f"\nDeals for Position {position_id}:")
        for d in target_deals:
            print(f"  Deal ID: {d.get('id')}")
            print(f"    Type: {d.get('type')}")
            print(f"    Entry: {d.get('entry')}")
            print(f"    Profit: {d.get('profit')}")
            print(f"    Volume: {d.get('volume')}")
            print(f"    Time: {d.get('time')}")
            print("-" * 20)

if __name__ == "__main__":
    # From logs: 55922828539
    pos_id = "55922828539"
    asyncio.run(debug_position_history(pos_id))
