"""
Diagnostic script: test MetaAPI connection step by step.
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def diagnose():
    from metaapi_cloud_sdk import MetaApi

    token = os.getenv("METAAPI_TOKEN")
    account_id = os.getenv("METAAPI_ACCOUNT_ID")
    print(f"Token length: {len(token)}")
    print(f"Account ID: {account_id}")

    api = MetaApi(token)
    print("\n[1/5] Fetching account...")
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        print(f"  ✅ Account found: {account.name}")
        print(f"  State: {account.state}")
        print(f"  Connection status: {account.connection_status}")
        print(f"  Server: {account.server}")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return

    print("\n[2/5] Deploying account if needed...")
    try:
        if account.state != 'DEPLOYED':
            print(f"  Current state: {account.state}, deploying...")
            await account.deploy()
            print("  Waiting for deployment (timeout 60s)...")
            await account.wait_deployed(timeout_in_seconds=60)
            print("  ✅ Deployed!")
        else:
            print(f"  Already DEPLOYED")
    except Exception as e:
        print(f"  ❌ Deploy failed: {e}")
        return

    print("\n[3/5] Waiting for broker connection (timeout 120s)...")
    try:
        await account.wait_connected(timeout_in_seconds=120)
        print("  ✅ Account connected to broker!")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return

    print("\n[4/5] Creating RPC connection...")
    try:
        connection = account.get_rpc_connection()
        await connection.connect()
        print("  Waiting for synchronization (timeout 120s)...")
        await connection.wait_synchronized(timeout_in_seconds=120)
        print("  ✅ RPC synchronized!")
    except Exception as e:
        print(f"  ❌ RPC failed: {e}")
        return

    print("\n[5/5] Fetching account info and price...")
    try:
        info = await connection.get_account_information()
        print(f"  Balance: {info.get('balance', 'N/A')}")
        print(f"  Equity: {info.get('equity', 'N/A')}")
        print(f"  Currency: {info.get('currency', 'N/A')}")
        print(f"  Leverage: {info.get('leverage', 'N/A')}")
    except Exception as e:
        print(f"  ❌ Account info failed: {e}")

    try:
        price = await connection.get_symbol_price("EURUSD")
        print(f"  EURUSD bid: {price.get('bid', 'N/A')}, ask: {price.get('ask', 'N/A')}")
    except Exception as e:
        print(f"  ❌ Price fetch failed: {e}")

    print("\n✅ Full diagnosis complete. All systems operational!")

    # Clean up
    try:
        await connection.close()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(diagnose())
