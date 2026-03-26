
import asyncio
from datetime import datetime, timedelta, timezone
from app.core.broker.metaapi_client import broker

async def debug_history_wide():
    print("Connecting to MetaAPI...")
    await broker.connect()
    
    # Try 30 days with simplified ISO format
    start = datetime.now(timezone.utc) - timedelta(days=30)
    start_str = start.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    print(f"Querying from {start_str} to {end_str}")
    
    data = await broker._get(
        "/history-deals/time",
        params={
            "startTime": start_str,
            "endTime": end_str
        }
    )
    
    if data:
        print(f"Total deals found: {len(data)}")
        if isinstance(data, list) and len(data) > 0:
            for d in data[:5]:
                print(f"Deal ID: {d.get('id')}, Position ID: {d.get('positionId')}, Symbol: {d.get('symbol')}, Profit: {d.get('profit')}")
    else:
        print("No data returned or error occurred.")
        
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_history_wide())
