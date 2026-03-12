"""
Debug: Find all available connection methods in the MetaAPI SDK v28
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def debug():
    from metaapi_cloud_sdk import MetaApi

    token = os.getenv("METAAPI_TOKEN")
    account_id = os.getenv("METAAPI_ACCOUNT_ID")

    api = MetaApi(token)
    account = await api.metatrader_account_api.get_account(account_id)
    
    print("=== Account attributes ===")
    attrs = [a for a in dir(account) if not a.startswith('_')]
    for a in attrs:
        print(f"  {a}")
    
    print("\n=== Connection methods ===")
    conn_methods = [a for a in attrs if 'connect' in a.lower() or 'rpc' in a.lower() or 'streaming' in a.lower()]
    for m in conn_methods:
        print(f"  {m}: {type(getattr(account, m))}")

    # Try streaming connection instead
    print("\n=== Trying streaming connection ===")
    try:
        connection = account.get_streaming_connection()
        print(f"  Got streaming connection: {type(connection)}")
        print(f"  Streaming methods: {[a for a in dir(connection) if not a.startswith('_')]}")
    except Exception as e:
        print(f"  Streaming failed: {e}")

    # Check if there's a REST connection
    print("\n=== MetaApi top-level attributes ===")
    api_attrs = [a for a in dir(api) if not a.startswith('_')]
    for a in api_attrs:
        print(f"  {a}")

if __name__ == "__main__":
    asyncio.run(debug())
