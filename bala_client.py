import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

BALA_BASE_URL = os.getenv("BALA_BASE_URL", "https://158.247.231.14/api/v1")
BALA_API_KEY = os.getenv("BALA_API_KEY")


class BalaClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            "X-API-Key": BALA_API_KEY,
            "Content-Type": "application/json",
        }

    async def catalog(self):
        # Отключаем SSL проверку, так как BALA работает по IP (158.247.231.14)
        async with self.session.get(
            f"{BALA_BASE_URL}/catalog",
            headers=self.headers,
            timeout=20,
            ssl=False
        ) as r:
            r.raise_for_status()
            return await r.json()

    async def create_order(self, order_id: str, customer_ref: str, product_id: int, max_price: int):
        headers = {**self.headers, "Idempotency-Key": order_id}
        payload = {
            "customer_ref": customer_ref,
            "product_id": product_id,
            "max_price_pcoins": max_price,
        }
        async with self.session.post(
            f"{BALA_BASE_URL}/orders",
            json=payload,
            headers=headers,
            timeout=30,
            ssl=False
        ) as r:
            try:
                data = await r.json()
            except Exception:
                data = await r.text()
            return data, r.status

    async def order_status(self, request_id: str):
        params = {"request_id": request_id}
        async with self.session.get(
            f"{BALA_BASE_URL}/orders/status",
            params=params,
            headers=self.headers,
            timeout=20,
            ssl=False
        ) as r:
            r.raise_for_status()
            return await r.json()

    async def customer_keys(self, customer_ref: str):
        params = {"customer_ref": customer_ref}
        async with self.session.get(
            f"{BALA_BASE_URL}/customers/keys",
            params=params,
            headers=self.headers,
            timeout=20,
            ssl=False
        ) as r:
            r.raise_for_status()
            return await r.json()