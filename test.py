import asyncio
import aiohttp
from bala_client import BalaClient
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    async with aiohttp.ClientSession() as s:
        c = BalaClient(s)
        try:
            data = await c.catalog()
            print("API ЖАУАБЫ:")
            print(data)
        except Exception as e:
            print("API ҚАТЕСІ:", e)

if __name__ == "__main__":
    asyncio.run(test())