import asyncio
from metaapi_cloud_sdk import MetaApi
import os
from dotenv import load_dotenv

load_dotenv()

async def get_id():
    token = os.getenv("METAAPI_TOKEN")
    api = MetaApi(token)
    try:
        # Use pagination method if get_accounts is missing
        accounts = await api.metatrader_account_api.get_accounts_with_infinite_scroll_pagination()
        if not accounts:
            print("No accounts found.")
            return
        
        for account in accounts:
            print(f"ID: {account.id} | Name: {account.name}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(get_id())
