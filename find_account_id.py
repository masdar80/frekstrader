import asyncio
from metaapi_cloud_sdk import MetaApi
import os
from dotenv import load_dotenv

load_dotenv()

async def list_accounts():
    token = os.getenv("METAAPI_TOKEN")
    if not token or token == "put_your_metaapi_token_here":
        print("Error: No MetaAPI token found in .env")
        return

    api = MetaApi(token)
    try:
        metatrader_accounts = await api.metatrader_account_api.get_accounts()
        if not metatrader_accounts:
            print("No MetaTrader accounts found. Please add an account in MetaAPI dashboard.")
            return

        print("\n--- MetaTrader Accounts Found ---")
        for account in metatrader_accounts:
            print(f"ID: {account.id} | Server: {account.server} | Magic: {account.magic} | State: {account.state}")
        print("---------------------------------\n")
    except Exception as e:
        print(f"Failed to fetch accounts: {e}")

if __name__ == "__main__":
    asyncio.run(list_accounts())
