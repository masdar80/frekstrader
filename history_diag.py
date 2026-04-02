import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Add root to path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker
from app.config import settings

async def diagnose():
    print("--- 🔎 HISTORY DIAGNOSTIC ---")
    connected = await broker.connect()
    if not connected:
        print("❌ Failed to connect to broker.")
        return

    history = await broker.get_history(days=7)
    print(f"Total history deals found: {len(history)}")
    
    # Check for the IDs we are looking for
    TargetIDs = ["56011396572", "56036385789", "56036429791", "56036483938", "56036517109", "56024645411"]
    
    found_count = 0
    for deal in history:
        pid = str(deal.get("position_id"))
        if pid in TargetIDs:
            print(f"  ✅ FOUND DEAL for Position {pid}: Profit {deal.get('profit')}, Type {deal.get('entry_type')}")
            found_count += 1
            
    if found_count == 0:
        print("  ❌ NONE of the targeted IDs were found in the last 7 days of history.")
        if history:
            print("  Sample Deal from history:")
            print(json.dumps(history[0], indent=2))
    else:
        print(f"  ✨ Found {found_count} matching deals.")

if __name__ == "__main__":
    asyncio.run(diagnose())
