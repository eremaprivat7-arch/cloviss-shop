import asyncio, os, uuid, aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bala_client import BalaClient

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8229076909
SUPPORT_USERNAME = "@osinxff"

MARKUP = 1.15
RATE_KZT = 6.25
REF_BONUS = 5

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
users_db = {}

# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================
def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Каталог товаров", callback_data="catalog")
    builder.button(text="💳 Пополнить баланс", callback_data="deposit")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="🔑 Мои ключи", callback_data="mykeys")
    builder.button(text="🎁 Рефералы", callback_data="ref")
    builder.button(text="🆘 Поддержка 24/7", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

@dp.message(Command("start"))
async def start(m: Message, command: CommandObject):
    user_id = m.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"invited_by": None, "ref_count": 0, "ref_earned": 0}
        if command.args and command.args.startswith("ref_"):
            try:
                inviter_id = int(command.args.split("_")[1])
                if inviter_id != user_id:
                    users_db[user_id]["invited_by"] = inviter_id
                    if inviter_id in users_db:
                        users_db[inviter_id]["ref_count"] += 1
                        users_db[inviter_id]["ref_earned"] += REF_BONUS
                    else:
                        users_db[inviter_id] = {"invited_by": None, "ref_count": 1, "ref_earned": REF_BONUS}
            except: pass

    text = f"👋 Привет, <b>{m.from_user.first_name}</b>!\n\nВыбери раздел ниже 👇"
    await m.answer(text, reply_markup=get_main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(call: CallbackQuery):
    await call.message.edit_text("Выбери раздел ниже 👇", reply_markup=get_main_menu(), parse_mode="HTML")

# ==========================================
# КАТАЛОГ (ЗАГРУЗКА И СОРТИРОВКА)
# ==========================================
@dp.callback_query(F.data == "catalog")
async def catalog(call: CallbackQuery):
    await call.message.edit_text("⏳ Загружаю каталог...")
    
    # Отключаем SSL для IP-адреса BALA
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as s:
        try:
            data = await BalaClient(s).catalog()
            products = data.get("products", [])
        except aiohttp.ClientConnectorError as e:
            await call.message.edit_text(f"❌ Ошибка сети: Сервер BALA недоступен.\n{e}")
            return
        except aiohttp.ClientResponseError as e:
            await call.message.edit_text(f"❌ Ошибка API: {e.status} {e.message}\nПроверь API ключ!")
            return
        except Exception as e:
            await call.message.edit_text(f"❌ Ошибка: {type(e).__name__} - {e}")
            return

    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 Android", callback_data="plat_Android")
    builder.button(text="🍏 iPhone", callback_data="plat_iOS")
    builder.button(text="💻 PC", callback_data="plat_PC")
    builder.button(text="📦 Other", callback_data="plat_Other")
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(2, 2, 1)
    
    await call.message.edit_text("📁 <b>Каталог</b>\nВыбери категорию:", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("plat_"))
async def show_platform(call: CallbackQuery):
    platform = call.data.split("_")[1]
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as s:
        data = await BalaClient(s).catalog()
        products = data.get("products", [])

    filtered = []
    for p in products:
        name = p['name'].upper()
        
        # Спец-товары AIM
        if any(x in name for x in ["AIMBODY", "AIMNECK", "AIMDRAG"]):
            if platform == "iOS": filtered.append(p)
            continue

        is_android = any(x in name for x in ["ANDROID", "APK"])
        is_ios = any(x in name for x in ["IOS", "IPHONE", "CERT", "MIGUL", "VELORA", "DELTA"])
        is_pc = any(x in name for x in ["PC", "DUSTU", "SPOOFER", "HWID"])

        if platform == "Android" and is_android:
            filtered.append(p)
        elif platform == "iOS" and is_ios:
            filtered.append(p)
        elif platform == "PC" and is_pc and not is_android and not is_ios:
            filtered.append(p)
        elif platform == "Other" and not (is_android or is_ios or is_pc):
            filtered.append(p)

    # Простая группировка: отрезаем сроки
    cheats = {}
    for p in filtered:
        name = p['name']
        # Пытаемся отрезать всё, что начинается с цифры (срок)
        # Например: "ANGRY MOD ROOT 1 Day" -> отрезаем "1 Day"
        parts = name.split()
        cheat_name = []
        for word in parts:
            if word[0].isdigit(): # если слово начинается с цифры
                break # останавливаемся
            cheat_name.append(word)
        
        cheat_str = " ".join(cheat_name).strip()
        if not cheat_str: cheat_str = "Unknown"
        
        # Спец-обработка AIM
        if "AIMBODY" in name.upper(): cheat_str = "AIMBODY"
        elif "AIMNECK" in name.upper(): cheat_str = "AIMNECK"
        elif "AIMDRAG" in name.upper(): cheat_str = "AIMDRAG"

        if cheat_str not in cheats:
            cheats[cheat_str] = []
        cheats[cheat_str].append(p)

    builder = InlineKeyboardBuilder()
    for cheat, items in cheats.items():
        builder.button(text=f"🎮 {cheat}", callback_data=f"cheat_{platform}_{cheat}")
        
    builder.button(text="⬅️ Назад", callback_data="catalog")
    builder.adjust(2)
    
    await call.message.edit_text(f"📱 <b>{platform}</b>\nВыбери мод:", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("cheat_"))
async def show_cheat_days(call: CallbackQuery):
    _, platform, cheat_name = call.data.split("_")
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as s:
        data = await BalaClient(s).catalog()
        products = data.get("products", [])

    items = [p for p in products if cheat_name.upper() in p['name'].upper()]

    builder = InlineKeyboardBuilder()
    
    if cheat_name in ["AIMBODY", "AIMNECK", "AIMDRAG"]:
        target_item = next((p for p in items if "15" in p['name']), None)
        if target_item:
            builder.button(text=f"🛒 15 Дней | 1500 ₸", callback_data=f"buy_{target_item['id']}_{target_item['price_pcoins']}_1500")
        else:
            builder.button(text="Нет в наличии", callback_data="catalog")
    else:
        for p in items:
            # Убираем название мода, чтобы оставить только срок
            display_name = p['name'].replace(cheat_name, "").strip(" -_")
            if not display_name: display_name = p['name']
            
            final_price = int((p["price_pcoins"] * MARKUP) * RATE_KZT)
            builder.button(text=f"🛒 {display_name} | {final_price} ₸", callback_data=f"buy_{p['id']}_{p['price_pcoins']}_{final_price}")
    
    builder.button(text="⬅️ Назад", callback_data=f"plat_{platform}")
    builder.adjust(1)
    
    await call.message.edit_text(f"🎮 <b>{cheat_name}</b>\nВыбери срок:", reply_markup=builder.as_markup(), parse_mode="HTML")

# ==========================================
# ПОКУПКА
# ==========================================
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    _, product_id, price_pcoins, final_price = call.data.split("_")
    product_id = int(product_id)
    price_pcoins = int(price_pcoins)
    final_price = int(final_price)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Оплатить (Тест)", callback_data=f"confirm_{product_id}_{price_pcoins}")
    builder.button(text="❌ Отмена", callback_data="catalog")
    builder.adjust(1)
    await call.message.edit_text(f"🛒 К оплате: <b>{final_price} ₸</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_order(call: CallbackQuery):
    _, product_id, price_pcoins = call.data.split("_")
    product_id = int(product_id)
    price_pcoins = int(price_pcoins)
    
    await call.message.edit_text("⏳ Создаю заказ...")
    order_id = "order_" + uuid.uuid4().hex[:12]
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as s:
        c = BalaClient(s)
        resp, status = await c.create_order(order_id=order_id, customer_ref="telegram_" + str(call.from_user.id), product_id=product_id, max_price=price_pcoins)
    
    if status in (200, 201):
        key_value = resp.get("key") or resp.get("license_key") or "Ключ не найден"
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ В меню", callback_data="main_menu")
        await call.message.edit_text(f"✅ <b>Успешно!</b>\n\nКлюч:\n<code>{key_value}</code>", reply_markup=builder.as_markup(), parse_mode="HTML")
        try:
            await bot.send_message(ADMIN_ID, f"💰 <b>Продажа!</b>\nКлиент: {call.from_user.first_name}\nID: <code>{call.from_user.id}</code>\nКлюч: <code>{key_value}</code>", parse_mode="HTML")
        except: pass
    else:
        await call.message.edit_text(f"❌ Ошибка: {resp}")

# ==========================================
# ПРОЧЕЕ
# ==========================================
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Пополнить", callback_data="deposit")
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    builder.adjust(1)
    await call.message.edit_text(f"👑 <b>Профиль</b>\nID: <code>{call.from_user.id}</code>\nБаланс: 0 ₸", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🆘 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    builder.adjust(1)
    await call.message.edit_text("💳 <b>Пополнение</b>\n\nНапиши в поддержку для оплаты.", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "mykeys")
async def mykeys(call: CallbackQuery):
    await call.message.edit_text("⏳ Загрузка...")
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as s:
        try:
            data = await BalaClient(s).customer_keys("telegram_" + str(call.from_user.id))
        except Exception as e:
            await call.message.edit_text(f"❌ Ошибка: {e}")
            return
    keys = data.get("keys", [])
    text = "🔑 <b>Ключи</b>\n\nНет ключей" if not keys else "🔑 <b>Ключи</b>\n\n"
    if keys:
        for k in keys: text += f"<code>{k.get('key')}</code>\n"
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "ref")
async def referral(call: CallbackQuery):
    user_id = call.from_user.id
    user_data = users_db.get(user_id, {"ref_count": 0, "ref_earned": 0})
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    await call.message.edit_text(f"🎁 <b>Рефералы</b>\nЗа друга: +5 ₸\nПриглашено: {user_data.get('ref_count', 0)}\nЗаработано: {user_data.get('ref_earned', 0)} ₸\n\n<code>{ref_link}</code>", reply_markup=builder.as_markup(), parse_mode="HTML")

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())