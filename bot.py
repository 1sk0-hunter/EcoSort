import sys
import time
import hashlib
import telebot
from telebot import types

# Обеспечиваем корректный вывод UTF-8 в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
import database
import ai_classifier
import anti_fraud

# Инициализация базы данных
database.init_db()

# Проверка токена Telegram
if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
    print("=" * 60)
    print("ВНИМАНИЕ: Токен TELEGRAM_BOT_TOKEN не задан в файле .env!")
    print("Откройте файл Desktop/EcoSort/.env и вставьте токен от @BotFather")
    print("=" * 60)

bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN or "DUMMY_TOKEN")

def get_main_keyboard():
    """Главная клавиатура бота (Zero-Click интерфейс)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_photo = types.KeyboardButton("📸 Сдать отход (Отправить фото)")
    btn_profile = types.KeyboardButton("👤 Мой профиль")
    btn_top = types.KeyboardButton("🏆 Топ лидеров")
    markup.add(btn_photo)
    markup.add(btn_profile, btn_top)
    return markup

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    user = database.get_or_create_user(user_id, username, first_name)

    welcome_text = (
        f"👋 Привет, {first_name}!\n\n"
        "🌿 Добро пожаловать в **EcoSort** — систему умного раздельного сбора отходов!\n\n"
        "⚡ **Вам больше не нужно выбирать контейнеры вручную:**\n"
        "1. Просто сделайте и отправьте фото предмета в этот чат\n"
        "2. Компьютерное зрение EcoSort определит материал\n"
        "3. Нужная створка бака (Пластик, Стекло, Бумага, Металл) **откроется автоматически**!\n"
        "4. Встроенные весы контейнера зафиксируют вес отхода, и баллы начислятся исходя из веса по тарифу.\n\n"
        f"💰 Ваш текущий баланс: **{user['points']} Экопоинтов**."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# Эластичный хэндлер для кнопки сдачи отходов (срабатывает на любые варианты старых и новых кнопок)
@bot.message_handler(func=lambda msg: msg.text and any(w in msg.text.lower() for w in ["сдать", "отход", "фото", "📸", "♻️"]))
def handle_photo_prompt(message):
    prompt_text = (
        "📸 **Сфотографируйте отход и отправьте фото в этот чат!**\n\n"
        "Ничего нажимать и выбирать не нужно: система сама распознает предмет и откроет нужный контейнер."
    )
    bot.send_message(message.chat.id, prompt_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "💡 Экономия памяти телефона")
def handle_memory_tip(message):
    memory_text = (
        "💡 **КАК СДАВАТЬ МУСОР И НЕ ЗАСОРЯТЬ ПАМЯТЬ ТЕЛЕФОНА:**\n"
        "────────────────────\n"
        "1. **Быстрая съемка в Telegram:**\n"
        "Нажмите 📎 (скрепка) → значок Камеры → сделайте фото и отправьте. "
        "Снимок сразу отправляется на анализ и **НЕ сохраняется в фотопленку смартфона**.\n\n"
        "2. **Настройки галереи Telegram:**\n"
        "Проверьте: *Настройки → Данные и память → Сохранять в галерее → Отключить для личных чатов*.\n\n"
        "3. **Аппаратный концепт EcoSort (Для презентации):**\n"
        "В серийной версии урны камера **ESP32-CAM** встроена прямо в лоток бака. "
        "Пользователь только авторизуется, а камера бака сама фотографирует предмет. Память смартфона не расходуется вообще!\n"
        "────────────────────"
    )
    bot.send_message(message.chat.id, memory_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # 1. УРОВЕНЬ ЗАЩИТЫ 1: Кулдаун между сдачами (20 секунд)
    can_submit, wait_sec = database.check_user_cooldown(user_id, cooldown_seconds=20)
    if not can_submit:
        bot.send_message(
            chat_id,
            f"⏳ **Слишком частая отправка (Rate Limit)!**\n\n"
            f"В целях безопасности между сдачами установлен интервал.\n"
            f"Пожалуйста, подождите **{wait_sec} сек.** перед следующей сдачей отхода.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    status_msg = bot.send_message(chat_id, "🔍 *Анализ отхода компьютерным зрением EcoSort...*", parse_mode="Markdown")

    try:
        # Скачиваем изображение наилучшего разрешения
        photo_info = bot.get_file(message.photo[-1].file_id)
        image_bytes = bot.download_file(photo_info.file_path)

        # 2. УРОВЕНЬ ЗАЩИТЫ 2: Точный Anti-Fraud (SHA-256)
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        if database.is_sha256_exists(image_hash):
            bot.edit_message_text(
                "🛡️ **ОТКАЗ СИСТЕМЫ БЕЗОПАСНОСТИ (Anti-Fraud: Replay Attack)!**\n\n"
                "⚠️ **Обнаружена повторная отправка идентичного файла.**\n"
                "Эта фотография уже была использована ранее для начисления очков.\n\n"
                "Пожалуйста, сфотографируйте реальный новый предмет.",
                chat_id=chat_id,
                message_id=status_msg.message_id,
                parse_mode="Markdown"
            )
            return

        # 3. УРОВЕНЬ ЗАЩИТЫ 3: Перцептивный хеш dHash (повтор с другого угла)
        current_dhash = anti_fraud.compute_dhash(image_bytes)
        recent_hashes = database.get_recent_dhashes(limit=300)
        perceptual_dup = anti_fraud.find_perceptual_duplicate(current_dhash, recent_hashes, threshold=10)
        
        if perceptual_dup:
            matched_hash, dist = perceptual_dup
            bot.edit_message_text(
                "🛡️ **ОТКАЗ СИСТЕМЫ БЕЗОПАСНОСТИ (Anti-Fraud: Perceptual Match)!**\n\n"
                "⚠️ **Обнаружена повторная съемка того же предмета с другого ракурса!**\n"
                f"Алгоритм перцептивного хеширования выявил совпадение текстуры и формы (дистанция {dist}/64) с ранее сданным предметом.\n\n"
                "Повторное начисление очков за один и тот же предмет заблокировано.",
                chat_id=chat_id,
                message_id=status_msg.message_id,
                parse_mode="Markdown"
            )
            return

        # 4. УРОВЕНЬ ЗАЩИТЫ 4: Анализ через компьютерное зрение EcoSort + Anti-Spoofing
        ai_result = ai_classifier.analyze_waste_image(image_bytes)

        if not ai_result.get("success"):
            bot.edit_message_text(
                f"❌ **Ошибка распознавания:**\n{ai_result.get('error')}",
                chat_id=chat_id,
                message_id=status_msg.message_id
            )
            return

        data = ai_result["data"]
        is_screen_or_stock = data.get("is_screen_or_stock", False)
        fraud_reason = data.get("fraud_reason")
        is_waste = data.get("is_waste", False)
        detected_category = data.get("category", "other")
        material_name = data.get("material_name", "Неопределенный предмет")
        description = data.get("description", "")
        confidence = data.get("confidence", 0)

        # 4.1. Проверка на фото экрана или картинку из интернета
        if is_screen_or_stock:
            bot.edit_message_text(
                "🛡️ **ОТКАЗ СИСТЕМЫ БЕЗОПАСНОСТИ (Anti-Spoofing: Screen/Stock Detect)!**\n\n"
                f"⚠️ **Причина:** {fraud_reason or 'Обнаружена съемка с экрана монитора или картинка из интернета'}.\n\n"
                "Для начисления очков требуется физическое присутствие и реальный предмет у контейнера, а не цифровое фото с дисплея.",
                chat_id=chat_id,
                message_id=status_msg.message_id,
                parse_mode="Markdown"
            )
            return

        # 4.2. Проверка: является ли это отходом вообще
        if not is_waste:
            bot.edit_message_text(
                "❌ **Предмет не является бытовым отходом!**\n\n"
                f"🤖 Система определила: *{material_name}*\n"
                f"📝 Пояснение: {description}\n\n"
                "Пожалуйста, направьте камеру на вторсырье (бутылку, банку, картон).",
                chat_id=chat_id,
                message_id=status_msg.message_id,
                parse_mode="Markdown"
            )
            return

        # 5. АВТОМАТИЧЕСКАЯ МАРШРУТИЗАЦИЯ И ИНФОРМАЦИЯ О ВЕСАХ
        if detected_category in config.CONTAINERS:
            container = config.CONTAINERS[detected_category]
            points = container["points"]

            new_balance = database.record_submission(
                user_id=user_id,
                container_id=detected_category,
                detected_material=material_name,
                points=points,
                image_hash=image_hash,
                dhash=current_dhash
            )

            success_text = (
                "🎉 **ПРЕДМЕТ УСПЕШНО РАСПОЗНАН!**\n\n"
                f"📦 **Обнаружено:** {material_name} (Точность: {confidence}%)\n"
                f"💡 **Описание:** {description}\n\n"
                f"🔓 **АВТОМАТИЧЕСКИ РАЗБЛОКИРОВАН:**\n"
                f"👉 **{container['name']}**\n"
                "Створка открыта! Можете опускать предмет в контейнер.\n\n"
                "⚖️ **ВЗВЕШИВАНИЕ И ТАРИФ:**\n"
                f"• Официальный тариф: **{container['tariff']}**\n"
                "• Опустите предмет в контейнер: встроенные весы зафиксируют точный вес отхода, и баллы начислятся исходя из веса по тарифу.\n\n"
                f"🌿 **Предмет зарегистрирован в системе!** (+{points} базовых очков)\n"
                f"💰 **Ваш общий баланс:** **{new_balance} Экопоинтов**"
            )
            bot.edit_message_text(
                success_text,
                chat_id=chat_id,
                message_id=status_msg.message_id,
                parse_mode="Markdown"
            )
        else:
            other_text = (
                "⚠️ **НЕСОРТИРУЕМЫЙ ОТХОД!**\n\n"
                f"🤖 Система определила предмет как: **{material_name}**\n"
                f"📝 Пояснение: {description}\n\n"
                "Данный вид отходов не подлежит раздельной переработке в умных контейнерах. "
                "Пожалуйста, опустите его в обычный бак для смешанных отходов."
            )
            bot.edit_message_text(
                other_text,
                chat_id=chat_id,
                message_id=status_msg.message_id,
                parse_mode="Markdown"
            )

    except Exception as e:
        bot.edit_message_text(
            f"❌ Непредвиденная ошибка при обработке: {str(e)}",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )

@bot.message_handler(func=lambda msg: msg.text == "👤 Мой профиль")
@bot.message_handler(commands=['profile'])
def handle_profile(message):
    user_id = message.from_user.id
    stats = database.get_user_stats(user_id)
    
    categories = stats.get("categories", {})
    plastic_cnt = categories.get("plastic", {}).get("count", 0)
    glass_cnt = categories.get("glass", {}).get("count", 0)
    paper_cnt = categories.get("paper", {}).get("count", 0)
    metal_cnt = categories.get("metal", {}).get("count", 0)

    profile_text = (
        "👤 **ЛИЧНЫЙ ЭКО-ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ**\n"
        "────────────────────\n"
        f"🆔 Ваш ID: `{user_id}`\n"
        f"💰 Баланс: **{stats['points']} Экопоинтов**\n"
        f"📦 Всего сдано предметов: **{stats['items_count']} шт.**\n\n"
        "📊 **Разбивка по фракциям:**\n"
        f"• 🟢 Пластик: **{plastic_cnt}** шт. (Тариф: 50 ₸/кг)\n"
        f"• 🔵 Стекло: **{glass_cnt}** шт. (Тариф: 5 ₸/кг)\n"
        f"• 🟡 Бумага / Картон: **{paper_cnt}** шт. (Тариф: 50–65 ₸/кг)\n"
        f"• 🔘 Металлические банки: **{metal_cnt}** шт. (Тариф: 150 ₸/кг)\n"
        "────────────────────\n"
        "🌿 *Сортируйте отходы в баки EcoSort и пополняйте баланс!*"
    )
    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "🏆 Топ лидеров")
@bot.message_handler(commands=['top'])
def handle_top(message):
    leaders = database.get_leaderboard(limit=5)
    if not leaders:
        bot.send_message(message.chat.id, "🏆 Рейтинг пока пуст. Будьте первым, кто сдаст вторсырье!", reply_markup=get_main_keyboard())
        return

    text = "🏆 **ТОП-5 ЭКО-ЛИДЕРОВ СИСТЕМЫ**\n────────────────────\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for i, user in enumerate(leaders):
        name = user["first_name"] or user["username"] or "Пользователь"
        text += f"{medals[i]} **{name}** — {user['points']} очков ({user['items_count']} шт.)\n"
        
    text += "────────────────────\nСдавайте отходы в баки EcoSort и поднимайтесь в рейтинге!"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['about'])
def handle_about(message):
    about_text = (
        "ℹ️ **О ПРОЕКТЕ ECOSORT**\n"
        "────────────────────\n"
        "**EcoSort** — цифровая система умного раздельного сбора отходов с распознаванием фракций и взвешиванием вторсырья.\n\n"
        "🛡️ **Команда проекта:**\n"
        "Инженеры по направлению «Информационная безопасность».\n\n"
        "⚙️ **Технологии проекта:**\n"
        "• Компьютерное зрение: Нейросетевая модель распознавания отходов EcoSort\n"
        "• Весовая платформа: Тензодатчики для учета фактического веса сданного вторсырья\n"
        "• 4 рубежа Anti-Fraud защиты от фиктивных сдач и фото с мониторов\n\n"
        "📍 Разработано для конкурса *Eco-Startup & IT Challenge 2026*."
    )
    bot.send_message(message.chat.id, about_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# Резервный хэндлер на любой неопознанный текст: возвращает пользователя к меню с актуальной клавиатурой
@bot.message_handler(content_types=['text'])
def handle_fallback(message):
    bot.send_message(
        message.chat.id,
        "👋 Чтобы сдать отход, просто **отправьте фото предмета** прямо в этот чат!",
        reply_markup=get_main_keyboard()
    )

if __name__ == "__main__":
    print("Запуск бота EcoSort (Zero-Click + Весовой расчет)...")
    print("Бот готов к обработке сообщений (Polling mode).")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"Критическая ошибка работы бота: {e}")
