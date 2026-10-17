import asyncio
import aiohttp
import os
from dotenv import load_dotenv
from bala_client import BalaClient, BALA_BASE_URL

load_dotenv()

async def test():
    async with aiohttp.ClientSession() as s:
        c = BalaClient(s)
        # Пробуем разные варианты endpoint'ов для баланса
        urls = [
            f"{BALA_BASE_URL}/balance",
            f"{BALA_BASE_URL}/me",
            f"{BALA_BASE_URL}/user",
            f"{BALA_BASE_URL}/profile",
            f"{BALA_BASE_URL}/wallet"
        ]
        for url in urls:
            try:
                async with s.get(url, headers=c.headers, timeout=5, ssl=False) as r:
                    print(f"URL: {url} -> Status: {r.status}")
                    if r.status == 200:
                        print("Response:", await r.text())
            except Exception as e:
                print(f"URL: {url} -> Error: {e}")

asyncio.run(test())