import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import qrcode
from PIL import Image, ImageDraw

# Папка для сохранения готовых QR-кодов
OUTPUT_DIR = Path(__file__).resolve().parent / "qr_codes"
OUTPUT_DIR.mkdir(exist_ok=True)

# Имя вашего бота в Telegram (замените на ваш юзернейм от @BotFather)
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "EcoSort_AI_bot")

CONTAINERS = [
    {
        "id": "bin_plastic",
        "name": "КОНТЕЙНЕР А: ПЛАСТИК",
        "sub": "ПЭТ-бутылки, стаканы, крышки",
        "color": (34, 197, 94),  # Зеленый
        "file": "qr_plastic.png"
    },
    {
        "id": "bin_glass",
        "name": "КОНТЕЙНЕР Б: СТЕКЛО",
        "sub": "Стеклянные бутылки, банки",
        "color": (59, 130, 246),  # Синий
        "file": "qr_glass.png"
    },
    {
        "id": "bin_paper",
        "name": "КОНТЕЙНЕР В: БУМАГА",
        "sub": "Картон, тетради, коробки",
        "color": (234, 179, 8),  # Желтый
        "file": "qr_paper.png"
    },
    {
        "id": "bin_metal",
        "name": "КОНТЕЙНЕР Г: МЕТАЛЛ",
        "sub": "Алюминиевые банки, жесть",
        "color": (148, 163, 184), # Серый
        "file": "qr_metal.png"
    }
]

def generate_qr_stickers():
    print(f"Генерация QR-кодов для бота: @{BOT_USERNAME}...")
    
    for item in CONTAINERS:
        link = f"https://t.me/{BOT_USERNAME}?start={item['id']}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(link)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        
        w, h = qr_img.size
        sticker = Image.new('RGB', (w, h + 80), color=(255, 255, 255))
        sticker.paste(qr_img, (0, 0))
        
        draw = ImageDraw.Draw(sticker)
        draw.rectangle([(0, h), (w, h + 80)], fill=item['color'])
        draw.text((w // 2, h + 25), item['name'], fill=(255, 255, 255), anchor="mm")
        draw.text((w // 2, h + 55), item['sub'], fill=(255, 255, 255), anchor="mm")
        
        file_path = OUTPUT_DIR / item['file']
        sticker.save(file_path)
        print(f"[OK] Создан: {file_path.name} -> {link}")

    print("\nВсе 4 QR-кода сохранены в папку: Desktop/EcoSort/qr_codes/")
    print("Распечатайте их или выведите на экран смартфона для демонстрации перед жюри!")

if __name__ == "__main__":
    generate_qr_stickers()
