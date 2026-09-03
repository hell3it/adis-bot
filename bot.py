import asyncio
import logging
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO)

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8712152425:AAGvZNVaFctzKPzz2BNSDkouhJ69QGs6dZc"
JSONBIN_KEY = "$2a$10$P1l9c6hF19G7WpMLt/TyCeFfmUF1hY0zUitagFtnrLzSwG4mntf/W"
BIN_ID = "6a95be10f5f4af5e2958d29e"

# Публичный адрес твоего сервиса на Render
RENDER_PUBLIC_URL = "https://adis-menu-bot.onrender.com"

ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "11111"

authenticated_admins = set()

ITEMS_CATALOG = [
    ("belyash", "Беляш с мясом", 130),
    ("sosiska", "Сосиска в тесте", 100),
    ("cheb_mix", "Чебурек Mix", 200),
    ("cheb_meat", "Чебурек с мясом", 150),
    ("cheb_cheese", "Чебурек с сыром", 150),
    ("khush_meat", "Хушуур с мясом", 130),
    ("khush_potato", "Хушуур с картофелем", 100),
    ("pie_apple", "Пирожок с яблоком", 50),
    ("pie_egg", "Пирожок с яйцом", 50),
    ("pie_potato", "Пирожок с картошкой", 50),
    ("pie_cabbage", "Пирожок с капустой", 50),
    ("pie_liver", "Пирожок с печенью", 50),
    ("pie_meat", "Пирожок с мясом", 50),
    ("vat_jam", "Ватрушка с джемом", 50),
    ("vat_curd", "Ватрушка с творогом", 50),
    ("panc_milk", "Блин со сгущенкой", 80),
    ("panc_jam", "Блин с джемом", 80),
    ("panc_sour", "Блин со сметаной", 80),
    ("panc_curd", "Блин с творогом", 100),
    ("panc_ham", "Блин с ветчиной/сыром", 110),
    ("panc_honey", "Блин с мёдом", 130),
    ("panc_plain", "Один блин", 25),
]

class AuthStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

class PriceStates(StatesGroup):
    waiting_for_new_price = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== РАБОТА С JSONBIN ====================
async def get_bin_data() -> dict:
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_KEY, "X-Bin-Meta": "false"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logging.error(f"Ошибка чтения JSONBin: {e}")
    return {"image_url": "", "out_of_stock": [], "prices": {}}

async def update_bin_data(data: dict) -> bool:
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=data, headers=headers) as resp:
                return resp.status == 200
    except Exception as e:
        logging.error(f"Ошибка записи JSONBin: {e}")
        return False

# ==================== КЛАВИАТУРЫ ====================
def get_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Обновить фото доски меню", callback_data="hint_photo")],
        [InlineKeyboardButton(text="📦 Стоп-лист (Наличие)", callback_data="open_stock")],
        [InlineKeyboardButton(text="💰 Редактор цен", callback_data="open_prices")],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="logout")]
    ])

def build_stock_keyboard(out_of_stock: list) -> InlineKeyboardMarkup:
    keyboard, row = [], []
    for item_id, item_name, _ in ITEMS_CATALOG:
        icon = "🔴" if item_id in out_of_stock else "🟢"
        row.append(InlineKeyboardButton(text=f"{icon} {item_name}", callback_data=f"toggle_{item_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_price_keyboard(current_prices: dict) -> InlineKeyboardMarkup:
    keyboard, row = [], []
    for item_id, item_name, default_price in ITEMS_CATALOG:
        price = current_prices.get(item_id, default_price)
        row.append(InlineKeyboardButton(text=f"{item_name}: {price}₽", callback_data=f"setprice_{item_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==================== АВТОРИЗАЦИЯ ====================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id in authenticated_admins:
        return await message.answer("Главное меню администратора:", reply_markup=get_main_menu())
    
    await state.clear()
    await message.answer(
        "🔒 <b>Панель управления кафе «Буузная Адис»</b>\n\n"
        "Для работы требуется авторизация.\n"
        "Введите <b>логин</b> сотрудника:",
        parse_mode="HTML"
    )
    await state.set_state(AuthStates.waiting_for_login)

@dp.message(AuthStates.waiting_for_login)
async def process_login(message: Message, state: FSMContext):
    await state.update_data(login=message.text.strip())
    try:
        await message.delete()
    except Exception:
        pass

    await message.answer("🔑 Теперь введите <b>пароль</b>:", parse_mode="HTML")
    await state.set_state(AuthStates.waiting_for_password)

@dp.message(AuthStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    user_data = await state.get_data()
    login = user_data.get("login")
    password = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        authenticated_admins.add(message.from_user.id)
        await state.clear()
        await message.answer(
            "✅ <b>Авторизация успешна!</b>\n\n"
            "• Чтобы изменить фото меню: просто <b>отправьте сюда фотографию</b> доски.\n"
            "• Или выберите раздел ниже:",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    else:
        await state.clear()
        await message.answer(
            "❌ <b>Неверные данные!</b> Доступ запрещен.\nДля повторной попытки нажмите /start",
            parse_mode="HTML"
        )

# ==================== СОХРАНЕНИЕ ФОТО МЕНЮ ====================
@dp.callback_query(F.data == "hint_photo")
async def cb_hint_photo(query: CallbackQuery):
    if query.from_user.id not in authenticated_admins:
        return await query.answer("Требуется вход через /start", show_alert=True)
    await query.message.answer("📷 Чтобы обновить доску меню, просто <b>отправьте фото</b> в этот чат как обычную картинку.", parse_mode="HTML")
    await query.answer()

@dp.message(F.photo)
async def handle_menu_photo(message: Message):
    if message.from_user.id not in authenticated_admins:
        return await message.answer("⚠️ Сначала войдите в систему через /start")

    status_msg = await message.answer("⏳ Сохраняю фотографию на сервере...")

    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file_info.file_path)
        
        # Сохраняем прямо на сервере Render
        menu_path = os.path.join(os.getcwd(), "menu.jpg")
        with open(menu_path, "wb") as f:
            f.write(file_bytes_io.read())

        # Формируем URL к нашему же серверу Render с меткой времени от кэша
        image_url = f"{RENDER_PUBLIC_URL}/menu.jpg?v={int(asyncio.get_event_loop().time())}"

        # Записываем ссылку в JSONBin
        bin_data = await get_bin_data()
        bin_data["image_url"] = image_url
        success = await update_bin_data(bin_data)

        if success:
            await status_msg.edit_text(
                "✅ <b>Фотография меню успешно сохранена!</b>\n\n"
                "Сервер начал прямую раздачу фото для сайта и мобильного приложения.",
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )
        else:
            await status_msg.edit_text("❌ Фото сохранено, но не удалось обновить базу JSONBin.")
    except Exception as e:
        logging.error(f"Ошибка при обработке фото: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при сохранении фото.")

# ==================== НАВИГАЦИЯ И СТОП-ЛИСТ ====================
@dp.callback_query(F.data == "back_main")
async def cb_back_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text("Главное меню администратора:", reply_markup=get_main_menu())
    await query.answer()

@dp.callback_query(F.data == "logout")
async def cb_logout(query: CallbackQuery, state: FSMContext):
    authenticated_admins.discard(query.from_user.id)
    await state.clear()
    await query.message.edit_text("🚪 Вы вышли из системы. Для входа нажмите /start")
    await query.answer()

@dp.callback_query(F.data == "open_stock")
async def cb_open_stock(query: CallbackQuery):
    if query.from_user.id not in authenticated_admins:
        return await query.answer("Требуется вход через /start", show_alert=True)
    data = await get_bin_data()
    out_of_stock = data.get("out_of_stock", [])
    await query.message.edit_text(
        "📦 <b>Управление наличием:</b>\n🟢 — есть в наличии\n🔴 — в стоп-листе\n<i>Нажмите, чтобы переключить:</i>",
        reply_markup=build_stock_keyboard(out_of_stock),
        parse_mode="HTML"
    )
    await query.answer()

@dp.callback_query(F.data.startswith("toggle_"))
async def cb_toggle_stock(query: CallbackQuery):
    if query.from_user.id not in authenticated_admins:
        return await query.answer("Доступ запрещен", show_alert=True)
    item_id = query.data.replace("toggle_", "")
    data = await get_bin_data()
    out_of_stock = data.get("out_of_stock", [])

    if item_id in out_of_stock:
        out_of_stock.remove(item_id)
        msg = "🟢 Блюдо включено"
    else:
        out_of_stock.append(item_id)
        msg = "🔴 Блюдо выключено"

    data["out_of_stock"] = out_of_stock
    await update_bin_data(data)
    await query.message.edit_reply_markup(reply_markup=build_stock_keyboard(out_of_stock))
    await query.answer(msg)

# ==================== РЕДАКТОР ЦЕН ====================
@dp.callback_query(F.data == "open_prices")
async def cb_open_prices(query: CallbackQuery):
    if query.from_user.id not in authenticated_admins:
        return await query.answer("Требуется вход через /start", show_alert=True)
    data = await get_bin_data()
    prices = data.get("prices", {})
    await query.message.edit_text(
        "💰 <b>Редактор цен</b>\nНажмите на позицию, цену которой хотите изменить:",
        reply_markup=build_price_keyboard(prices),
        parse_mode="HTML"
    )
    await query.answer()

@dp.callback_query(F.data.startswith("setprice_"))
async def cb_select_item_for_price(query: CallbackQuery, state: FSMContext):
    if query.from_user.id not in authenticated_admins:
        return await query.answer("Доступ запрещен", show_alert=True)

    item_id = query.data.replace("setprice_", "")
    item_name = next((name for i_id, name, _ in ITEMS_CATALOG if i_id == item_id), item_id)

    await state.update_data(edit_item_id=item_id, edit_item_name=item_name)
    await query.message.answer(
        f"✏️ Введите новую стоимость для позиции:\n<b>{item_name}</b> (только целое число в рублях):",
        parse_mode="HTML"
    )
    await state.set_state(PriceStates.waiting_for_new_price)
    await query.answer()

@dp.message(PriceStates.waiting_for_new_price)
async def process_new_price(message: Message, state: FSMContext):
    raw = message.text.strip().replace("₽", "").replace("руб", "").strip()
    if not raw.isdigit():
        return await message.answer("⚠️ Введите корректную сумму числом (например: <code>150</code>).", parse_mode="HTML")

    new_price = int(raw)
    data_state = await state.get_data()
    item_id = data_state.get("edit_item_id")
    item_name = data_state.get("edit_item_name")

    bin_data = await get_bin_data()
    prices = bin_data.get("prices", {})
    prices[item_id] = new_price
    bin_data["prices"] = prices
    await update_bin_data(bin_data)

    await state.clear()
    await message.answer(
        f"✅ Цена для <b>{item_name}</b> изменена на <b>{new_price} ₽</b>!",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

# ==================== ВЕБ-СЕРВЕР ====================
async def render_health_check(request):
    return web.Response(text="Bot is online and running!")

# Отдача самого файла фото меню сайту
async def serve_menu_image(request):
    menu_path = os.path.join(os.getcwd(), "menu.jpg")
    if os.path.exists(menu_path):
        return web.FileResponse(menu_path, headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache"
        })
    return web.Response(text="Image not found", status=404)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот управления «Буузная Адис» v2.4 запущен...")

    app = web.Application()
    app.router.add_get("/", render_health_check)
    app.router.add_get("/health", render_health_check)
    app.router.add_get("/menu.jpg", serve_menu_image)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
