import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных из .env в директории скрипта
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Токены
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Модель для компьютерного зрения
OPENAI_MODEL = "gpt-4o-mini"

# База данных SQLite
DB_PATH = BASE_DIR / "ecosort.db"

# Время жизни активной сессии (в секундах: 3 минуты)
SESSION_TIMEOUT_SECONDS = 180

# Конфигурация поддерживаемых контейнеров и тарифов по весу вторсырья
CONTAINERS = {
    "plastic": {
        "id": "plastic",
        "name": "🟢 Контейнер А: Пластик (ПЭТ)",
        "short_name": "Пластик (ПЭТ)",
        "description": "ПЭТ-бутылки, одноразовые стаканы, пластиковые флаконы, крышки",
        "tariff": "50 ₸/кг",
        "points": 10,
        "keywords": ["plastic", "пластик", "пэт", "pet", "полиэтилен", "бутылка"]
    },
    "glass": {
        "id": "glass",
        "name": "🔵 Контейнер Б: Стекло",
        "short_name": "Стекло",
        "description": "Стеклянные бутылки, банки, стеклянная тара",
        "tariff": "5 ₸/кг",
        "points": 5,
        "keywords": ["glass", "стекло", "стеклянная", "банка"]
    },
    "paper": {
        "id": "paper",
        "name": "🟡 Контейнер В: Бумага и картон",
        "short_name": "Бумага и картон",
        "description": "Картонные коробки, тетради, бумажные пакеты, листы А4",
        "tariff": "50–65 ₸/кг",
        "points": 10,
        "keywords": ["paper", "бумага", "картон", "cardboard", "газета"]
    },
    "metal": {
        "id": "metal",
        "name": "🔘 Контейнер Г: Металл и алюминий",
        "short_name": "Металлические банки",
        "description": "Алюминиевые банки от напитков, консервные банки",
        "tariff": "150 ₸/кг",
        "points": 15,
        "keywords": ["metal", "металл", "алюминий", "aluminum", "жесть", "банка"]
    }
}
