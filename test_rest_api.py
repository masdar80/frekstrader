"""
Quick test: find the correct REST API base URL and candle format
"""
import asyncio
import os
import httpx
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID")
HEADERS = {"auth-token": TOKEN, "Content-Type": "application/json"}

async def test():
    async with httpx.AsyncClient(timeout=30) as client:
        
        # Try provisioning API for base URL discovery
        print("=== Checking account URL ===")
        resp = await client.get(
            f"https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}",
            headers=HEADERS
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Region: {data.get('region')}")
            print(f"  Server: {data.get('server')}")
            print(f"  State: {data.get('state')}")
            print(f"  Connection status: {data.get('connectionStatus')}")
            # Look for client API URL hints
            print(f"  Keys: {list(data.keys())[:20]}")
        else:
            print(f"  Error {resp.status_code}: {resp.text[:300]}")

        # Try different base URLs for market data
        base_urls = [
            "https://mt-client-api-v1.london-b.agiliumtrade.ai",
            "https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai",
        ]
        
        for base in base_urls:
            print(f"\n=== Testing {base} ===")
            
            # Account info (with retry/longer timeout)
            print("  [account-info]")
            try:
                resp = await client.get(
                    f"{base}/users/current/accounts/{ACCOUNT_ID}/account-information",
                    headers=HEADERS, timeout=15
                )
                if resp.status_code == 200:
                    info = resp.json()
                    print(f"    ✅ Balance: {info.get('balance')}, Equity: {info.get('equity')}")
                else:
                    print(f"    Status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"    Error: {e}")
            
            # Symbol price
            print("  [symbol-price]")
            try:
                resp = await client.get(
                    f"{base}/users/current/accounts/{ACCOUNT_ID}/symbols/EURUSD/current-price",
                    headers=HEADERS
                )
                if resp.status_code == 200:
                    p = resp.json()
                    print(f"    ✅ Bid:{p.get('bid')} Ask:{p.get('ask')}")
                else:
                    print(f"    Status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"    Error: {e}")

            # Candles
            print("  [candles]")
            try:
                resp = await client.get(
                    f"{base}/users/current/accounts/{ACCOUNT_ID}/historical-market-data/symbols/EURUSD/timeframes/1h/candles",
                    params={"limit": 3},
                    headers=HEADERS
                )
                if resp.status_code == 200:
                    candles = resp.json()
                    print(f"    ✅ Got {len(candles)} candles")
                    for c in candles[:2]:
                        print(f"      {c}")
                else:
                    print(f"    Status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"    Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
