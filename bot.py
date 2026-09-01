import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Токены и конфигурация из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8712152425:AAGvZNVaFctzKPzz2BNSDkouhJ69QGs6dZc")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "b40d6e24694b8e8f8c49980d22dfb234")
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY", "$2a$10$7Z/Uv7dZ0jB7J8xT6rQkku5y0h2Y8aH9F9l1Z2b3C4d5E6f7G8h9I")
JSONBIN_BIN_ID = "6a95be10f5f4af5e2958d29e"

ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "11111"

# Состояния пользователей
authorized_users = set()
user_states = {}

def send_tg_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

@app.route("/", methods=["GET"])
def home():
    return "Adis Menu Bot is Active!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update or "message" not in update:
        return jsonify({"status": "ok"}), 200

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # Начало работы / Авторизация
    if text in ["/start", "/login"]:
        if chat_id in authorized_users:
            send_tg_message(chat_id, "✅ Вы уже авторизованы! Отправьте фотографию доски меню для обновления сайта.")
        else:
            user_states[chat_id] = "awaiting_login"
            send_tg_message(chat_id, "🔐 Введите логин для доступа к управлению меню:")
        return jsonify({"status": "ok"}), 200

    # Обработка ввода логина и пароля
    current_state = user_states.get(chat_id)

    if current_state == "awaiting_login":
        if text == ADMIN_LOGIN:
            user_states[chat_id] = "awaiting_password"
            send_tg_message(chat_id, "🔑 Логин принят. Введите пароль:")
        else:
            send_tg_message(chat_id, "❌ Неверный логин. Попробуйте еще раз или введите /login:")
        return jsonify({"status": "ok"}), 200

    if current_state == "awaiting_password":
        if text == ADMIN_PASSWORD:
            authorized_users.add(chat_id)
            user_states.pop(chat_id, None)
            send_tg_message(chat_id, "🎉 Авторизация успешна!\n\nТеперь просто отправьте сюда фото доски меню, и сайт обновится автоматически.")
        else:
            send_tg_message(chat_id, "❌ Неверный пароль. Попробуйте еще раз:")
        return jsonify({"status": "ok"}), 200

    # Защита от неавторизованных пользователей
    if chat_id not in authorized_users:
        send_tg_message(chat_id, "⛔ Доступ закрыт. Для входа напишите /login")
        return jsonify({"status": "ok"}), 200

    # Обработка фото (только для авторизованных)
    if "photo" in message:
        send_tg_message(chat_id, "⏳ Фото получено! Загружаю в облако и обновляю сайт...")
        
        photo_info = message["photo"][-1]
        file_id = photo_info["file_id"]

        # 1. Получение пути к файлу от Telegram
        file_res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}").json()
        file_path = file_res.get("result", {}).get("file_path")
        
        if not file_path:
            send_tg_message(chat_id, "❌ Ошибка скачивания фото от Telegram.")
            return jsonify({"status": "ok"}), 200

        tg_img_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        img_data = requests.get(tg_img_url).content

        # 2. Загрузка на ImgBB
        imgbb_res = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": img_data}
        ).json()

        uploaded_url = imgbb_res.get("data", {}).get("url")

        if uploaded_url:
            # 3. Обновление JSONBin
            headers = {
                "Content-Type": "application/json",
                "X-Master-Key": JSONBIN_API_KEY
            }
            jsonbin_res = requests.put(
                f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}",
                headers=headers,
                json={"image_url": uploaded_url}
            )

            if jsonbin_res.ok:
                send_tg_message(chat_id, f"✅ Меню на сайте успешно обновлено!\n\nСсылка: {uploaded_url}")
            else:
                send_tg_message(chat_id, "❌ Ошибка записи в базу данных.")
        else:
            send_tg_message(chat_id, "❌ Не удалось загрузить фото на сервер ImgBB.")

        return jsonify({"status": "ok"}), 200

    send_tg_message(chat_id, "📸 Пожалуйста, отправьте фотографию меню.")
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
