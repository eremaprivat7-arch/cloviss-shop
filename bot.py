import os
import sqlite3
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN жоқ! .env файлын тексер.")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(msg: types.Message):
    tg_id = msg.from_user.id
    username = msg.from_user.username or f"id{tg_id}"

    con = sqlite3.connect("shop.db")
    row = con.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if row:
        con.execute("UPDATE users SET username=? WHERE tg_id=?", (username, tg_id))
        text = f"Қайта келдің! TG ID: {tg_id}"
    else:
        con.execute(
            "INSERT INTO users(tg_id, username, role) VALUES(?,?,'buyer')",
            (tg_id, username),
        )
        text = f"Тіркелдің! TG ID: {tg_id}"
    con.commit()
    con.close()

    await msg.answer(text)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())