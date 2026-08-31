import os
import telebot
import requests
from threading import Thread
from flask import Flask

# Настройки ключей
TELEGRAM_BOT_TOKEN = "8712152425:AAGvZNVaFctzKPzz2BNSDkouhJ69QGs6dZc"
IMGBB_API_KEY = "c08f173c3969421ad6edd1a0a8248775"
JSONBIN_API_KEY = "$2a$10$P1l9c6hF19G7WpMLt/TyCeFfmUF1hY0zUitagFtnrLzSwG4mntf/W"
BIN_ID = "6a95be10f5f4af5e2958d29e"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Мини веб-сервер для хостинга
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот кафе Адис работает 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(
        message, 
        "👋 Привет! Я бот кафе «Адис».\n\n"
        "📸 Просто отправь мне свежую фотографию доски меню, и она моментально обновится на сайте у всех гостей!"
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    msg = bot.reply_to(message, "⏳ Фото получено! Загружаю и обновляю меню на сайте...")
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
            image_url = res_json["data"]["url"]

            headers = {
                "Content-Type": "application/json",
                "X-Master-Key": JSONBIN_API_KEY
            }
            requests.put(
                f"https://api.jsonbin.io/v3/b/{BIN_ID}",
                headers=headers,
                json={"image_url": image_url},
                timeout=15
            )

            bot.edit_message_text(
                f"✅ **Меню успешно обновлено у всех посетителей!**\n\n"
                f"🖼 Прямая ссылка:\n{image_url}\n\n"
                f"🌐 Проверь с любого устройства:\nhttps://adis-cafe38.netlify.app",
                chat_id=message.chat.id,
                message_id=msg.message_id,
                parse_mode="Markdown"
            )
        else:
            bot.edit_message_text("❌ Ошибка при загрузке на ImgBB.", chat_id=message.chat.id, message_id=msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)}", chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    print("🚀 Запуск бота кафе «Адис» в облаке...")
    # Запускаем веб-сервер в отдельном потоке
    server_thread = Thread(target=run_web)
    server_thread.daemon = True
    server_thread.start()
    
    # Запускаем прослушивание Telegram
    bot.infinity_polling()