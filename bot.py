import os
import telebot
import requests
from threading import Thread
from flask import Flask

# ==================== НАСТРОЙКИ ====================
TELEGRAM_BOT_TOKEN = "8712152425:AAGvZNVaFctzKPzz2BNSDkouhJ69QGs6dZc"
IMGBB_API_KEY = "c08f173c3969421ad6edd1a0a8248775"
JSONBIN_API_KEY = "$2a$10$P1l9c6hF19G7WpMLt/TyCeFfmUF1hY0zUitagFtnrLzSwG4mntf/W"
BIN_ID = "6a95be10f5f4af5e2958d29e"

ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "11111"

# Сессии
authenticated_admins = set()
user_states = {} # user_id: {"state": ..., "data": ...}

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

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот кафе Адис работает 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==================== JSONBIN ФУНКЦИИ ====================
def get_bin_data():
    headers = {"X-Master-Key": JSONBIN_API_KEY, "X-Bin-Meta": "false"}
    try:
        r = requests.get(f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error reading JSONBin: {e}")
    return {"image_url": "", "out_of_stock": [], "prices": {}}

def update_bin_data(data):
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY}
    try:
        r = requests.put(f"https://api.jsonbin.io/v3/b/{BIN_ID}", headers=headers, json=data, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Error updating JSONBin: {e}")
        return False

# ==================== КЛАВИАТУРЫ ====================
def main_menu_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("📸 Обновить фото доски меню", callback_data="hint_photo"))
    kb.add(telebot.types.InlineKeyboardButton("📦 Стоп-лист (Наличие)", callback_data="menu_stock"))
    kb.add(telebot.types.InlineKeyboardButton("💰 Редактор цен", callback_data="menu_prices"))
    kb.add(telebot.types.InlineKeyboardButton("🚪 Выйти", callback_data="menu_logout"))
    return kb

def stock_kb(out_of_stock):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for item_id, name, _ in ITEMS_CATALOG:
        icon = "🔴" if item_id in out_of_stock else "🟢"
        buttons.append(telebot.types.InlineKeyboardButton(f"{icon} {name}", callback_data=f"stock_{item_id}"))
    kb.add(*buttons)
    kb.add(telebot.types.InlineKeyboardButton("⬅️ В главное меню", callback_data="back_main"))
    return kb

def prices_kb(current_prices):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for item_id, name, default_price in ITEMS_CATALOG:
        price = current_prices.get(item_id, default_price)
        buttons.append(telebot.types.InlineKeyboardButton(f"{name}: {price}₽", callback_data=f"price_{item_id}"))
    kb.add(*buttons)
    kb.add(telebot.types.InlineKeyboardButton("⬅️ В главное меню", callback_data="back_main"))
    return kb

# ==================== ОБРАБОТКА КОМАНД И АВТОРИЗАЦИИ ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = message.from_user.id
    if uid in authenticated_admins:
        bot.send_message(message.chat.id, "Главное меню администратора:", reply_markup=main_menu_kb())
        return

    user_states[uid] = {"state": "LOGIN"}
    bot.send_message(
        message.chat.id,
        "🔒 <b>Панель управления кафе «Буузная Адис»</b>\n\nВведите <b>логин</b> сотрудника:",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("state") in ["LOGIN", "PASSWORD", "SET_PRICE"])
def handle_text_inputs(message):
    uid = message.from_user.id
    state_info = user_states.get(uid, {})
    state = state_info.get("state")
    text = message.text.strip()

    # Удаляем сообщение с введенным паролем или логином ради безопасности
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    if state == "LOGIN":
        user_states[uid] = {"state": "PASSWORD", "login": text}
        bot.send_message(message.chat.id, "🔑 Теперь введите <b>пароль</b>:", parse_mode="HTML")

    elif state == "PASSWORD":
        login = state_info.get("login")
        if login == ADMIN_LOGIN and text == ADMIN_PASSWORD:
            authenticated_admins.add(uid)
            user_states[uid] = {}
            bot.send_message(
                message.chat.id,
                "✅ <b>Авторизация успешна!</b>\n\n"
                "• Чтобы изменить доску: <b>просто отправь сюда фото</b>.\n"
                "• Или выбери действие ниже:",
                parse_mode="HTML",
                reply_markup=main_menu_kb()
            )
        else:
            user_states[uid] = {}
            bot.send_message(message.chat.id, "❌ Неверный логин или пароль. Нажмите /start для повтора.")

    elif state == "SET_PRICE":
        clean_price = text.replace("₽", "").replace("руб", "").strip()
        if not clean_price.isdigit():
            bot.send_message(message.chat.id, "⚠️ Введите корректную сумму числом (например: <code>150</code>).", parse_mode="HTML")
            return

        new_price = int(clean_price)
        item_id = state_info.get("item_id")
        item_name = state_info.get("item_name")

        bin_data = get_bin_data()
        prices = bin_data.get("prices", {})
        prices[item_id] = new_price
        bin_data["prices"] = prices
        update_bin_data(bin_data)

        user_states[uid] = {}
        bot.send_message(
            message.chat.id,
            f"✅ Цена для <b>{item_name}</b> изменена на <b>{new_price} ₽</b>!",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )

# ==================== ЗАГРУЗКА ФОТО (ПРОВЕРЕННЫЙ IMGBB) ====================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    if uid not in authenticated_admins:
        bot.reply_to(message, "⚠️ Сначала авторизуйтесь через /start")
        return

    msg = bot.reply_to(message, "⏳ Фото получено! Загружаю на CDN...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        res = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": downloaded_file},
            timeout=30
        )
        res_json = res.json()

        if res_json.get("success"):
            # Берем прямую ссылку на саму картинку (i.ibb.co)
            image_url = res_json["data"]["url"]

            # Сохраняем фото в JSONBin, НЕ стирая цены и стоп-лист
            bin_data = get_bin_data()
            bin_data["image_url"] = image_url
            update_bin_data(bin_data)

            bot.edit_message_text(
                f"✅ <b>Меню успешно обновлено!</b>\n\n"
                f"🖼 Фото открывается без VPN у всех клиентов.\n\n"
                f"🌐 Сайт: https://adis-cafe38.netlify.app",
                chat_id=message.chat.id,
                message_id=msg.message_id,
                parse_mode="HTML",
                reply_markup=main_menu_kb()
            )
        else:
            bot.edit_message_text("❌ Ошибка хостинга ImgBB. Попробуйте еще раз.", chat_id=message.chat.id, message_id=msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)}", chat_id=message.chat.id, message_id=msg.message_id)

# ==================== CALLBACK-КНОПКИ ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    if uid not in authenticated_admins:
        bot.answer_callback_query(call.id, "Требуется вход через /start", show_alert=True)
        return

    data = call.data

    if data == "back_main":
        user_states[uid] = {}
        bot.edit_message_text("Главное меню администратора:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=main_menu_kb())
        bot.answer_callback_query(call.id)

    elif data == "hint_photo":
        bot.send_message(call.message.chat.id, "📸 Просто отправь фото доски в этот чат как картинку.")
        bot.answer_callback_query(call.id)

    elif data == "menu_logout":
        authenticated_admins.discard(uid)
        user_states[uid] = {}
        bot.edit_message_text("🚪 Вы вышли. Нажмите /start для входа.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "menu_stock":
        bin_data = get_bin_data()
        out_of_stock = bin_data.get("out_of_stock", [])
        bot.edit_message_text(
            "📦 <b>Управление наличием:</b>\n🟢 — есть в наличии\n🔴 — в стоп-листе\n<i>Нажмите, чтобы изменить:</i>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=stock_kb(out_of_stock)
        )
        bot.answer_callback_query(call.id)

    elif data.startswith("stock_"):
        item_id = data.replace("stock_", "")
        bin_data = get_bin_data()
        out_of_stock = bin_data.get("out_of_stock", [])

        if item_id in out_of_stock:
            out_of_stock.remove(item_id)
            alert_text = "🟢 Блюдо включено"
        else:
            out_of_stock.append(item_id)
            alert_text = "🔴 Блюдо выключено"

        bin_data["out_of_stock"] = out_of_stock
        update_bin_data(bin_data)

        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=stock_kb(out_of_stock))
        bot.answer_callback_query(call.id, alert_text)

    elif data == "menu_prices":
        bin_data = get_bin_data()
        prices = bin_data.get("prices", {})
        bot.edit_message_text(
            "💰 <b>Редактор цен</b>\nВыберите позицию для изменения стоимости:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=prices_kb(prices)
        )
        bot.answer_callback_query(call.id)

    elif data.startswith("price_"):
        item_id = data.replace("price_", "")
        item_name = next((name for i_id, name, _ in ITEMS_CATALOG if i_id == item_id), item_id)
        user_states[uid] = {"state": "SET_PRICE", "item_id": item_id, "item_name": item_name}

        bot.send_message(
            call.message.chat.id,
            f"✏️ Введите новую цену для:\n<b>{item_name}</b> (в рублях, целое число):",
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("🚀 Запуск бота кафе «Адис» v2.5...")
    server_thread = Thread(target=run_web)
    server_thread.daemon = True
    server_thread.start()

    bot.infinity_polling(skip_pending=True)
