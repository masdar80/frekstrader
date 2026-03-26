
import asyncio
import os
from datetime import datetime, timedelta, timezone
import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID")
HEADERS = {"auth-token": TOKEN, "Content-Type": "application/json"}

async def test_endpoints():
    async with httpx.AsyncClient(timeout=30) as client:
        # Discovery
        resp = await client.get(
            f"https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}",
            headers=HEADERS
        )
        region = resp.json().get("region", "london")
        base_url = f"https://mt-client-api-v1.{region}-b.agiliumtrade.ai"
        
        endpoints = [
            "/history-deals",
            "/history-deals/time",
        ]
        
        start = datetime.now(timezone.utc) - timedelta(days=2)
        params = {
            "startTime": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
        
        for ep in endpoints:
            url = f"{base_url}/users/current/accounts/{ACCOUNT_ID}{ep}"
            print(f"Testing {url}...")
            r = await client.get(url, params=params, headers=HEADERS)
            print(f"  Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"  Success! Found {len(data)} items.")
                if data:
                    print(f"  First item keys: {list(data[0].keys())}")
                    # Print one item for inspection
                    # Find one with profit if possible
                    p_deal = next((d for d in data if d.get("profit") and d.get("profit") != 0), data[0])
                    print(f"  Sample Deal: {p_deal}")
            else:
                print(f"  Error: {r.text[:200]}")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
