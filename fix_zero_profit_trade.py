
import asyncio
import os
import sqlite3
from datetime import datetime, timedelta, timezone
import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID")
DATABASE_PATH = 'foreks.db'

async def repair_specific_trade(position_id):
    print(f"🔧 Repairing Position ID: {position_id}...")
    
    # 1. Connect to MetaAPI
    headers = {"auth-token": TOKEN, "Content-Type": "application/json"}
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Discovery
        resp = await client.get(
            f"https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}",
            headers=headers
        )
        region = resp.json().get("region", "london")
        base_url = f"https://mt-client-api-v1.{region}-b.agiliumtrade.ai"
        
        # Fetch deals for this position
        url = f"{base_url}/users/current/accounts/{ACCOUNT_ID}/history-deals/position/{position_id}"
        print(f"  Fetching deals from {url}...")
        resp = await client.get(url, headers=headers)
        
        if resp.status_code != 200:
            print(f"  ❌ Error fetching deals: {resp.status_code} {resp.text}")
            return

        deals = resp.json()
        if not deals:
            print(f"  ❌ No deals found for position {position_id}")
            return

        print(f"  Found {len(deals)} deals.")
        total_profit = 0.0
        close_price = 0.0
        
        for d in deals:
            p = d.get("profit", 0.0) + d.get("swap", 0.0) + d.get("commission", 0.0)
            total_profit += p
            if d.get("entry") in ["DEAL_ENTRY_OUT", "DEAL_ENTRY_INOUT"]:
                close_price = d.get("price", 0.0)
        
        if close_price == 0.0:
            close_price = deals[-1].get("price", 0.0)

        print(f"  ✨ Calculated Profit: ${total_profit:.2f}, Close Price: {close_price}")

    # 2. Update Local SQLite DB
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        
        # Update Trade
        cur.execute(
            "UPDATE trades SET profit = ?, close_price = ?, status = 'closed', closed_at = ? WHERE external_id = ?",
            (total_profit, close_price, datetime.now().isoformat(), position_id)
        )
        
        # Get trade ID to update decision
        cur.execute("SELECT id FROM trades WHERE external_id = ?", (position_id,))
        trade_row = cur.fetchone()
        if trade_row:
            trade_id = trade_row[0]
            cur.execute(
                "UPDATE decisions SET was_profitable = ? WHERE trade_id = ?",
                (total_profit > 0, trade_id)
            )
            print(f"  ✅ Updated Database for Trade ID {trade_id}")
        
        conn.commit()
        conn.close()
        print("🚀 Repair Complete!")
        
    except Exception as e:
        print(f"  ❌ DB Error: {e}")

if __name__ == "__main__":
    pos_id = "55922828539"
    asyncio.run(repair_specific_trade(pos_id))
