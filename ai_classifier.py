import json
import base64
import requests
from typing import Dict, Any
from config import OPENAI_API_KEY, OPENAI_MODEL

SYSTEM_PROMPT = """
Ты — экспертная система компьютерного зрения умного мусорного контейнера EcoSort с функциями Anti-Fraud защиты.
Твоя задача — классифицировать предмет на фотографии для раздельного сбора отходов и ВЫЯВЛЯТЬ ПОПЫТКИ ОБМАНА.

1. ПРОВЕРКА НА МОШЕННИЧЕСТВО (Anti-Spoofing / Anti-Fraud):
Определи, не пытается ли пользователь обмануть систему одним из способов:
- Съемка с экрана монитора, ноутбука, планшета или смартфона (признаки: муаровый узор, пиксельная сетка экрана, блики дисплея, рамки монитора, курсор мыши, интерфейс браузера).
- Скачанное изображение из интернета или стоковая фотография (признаки: идеальный белый изолированный студийный фон без теней, водяные знаки, 3D-рендер, отсутствие реального бытового окружения: руки, стола, пола или бака).

Если обнаружена съемка с экрана или сток: установи "is_screen_or_stock": true и укажи подробную причину в "fraud_reason".

2. КЛАССИФИКАЦИЯ МАТЕРИАЛА:
Выбери ровно одну категорию из списка:
- "plastic" : пластиковые бутылки, стаканчики, канистры, упаковка из полиэтилена, ПЭТ
- "glass"   : стеклянные бутылки, банки, битое стекло, стеклотара
- "paper"   : картонные коробки, тетради, газеты, бумажные пакеты, листы бумаги
- "metal"   : алюминиевые банки от напитков, консервы, металлические крышки
- "other"   : органика, пищевые отходы, текстиль, электроника, или если это не отход

Верни ответ СТРОГО в формате валидного JSON:
{
    "is_waste": true,
    "is_screen_or_stock": false,
    "fraud_reason": null,
    "category": "plastic",
    "material_name": "Пластиковая бутылка (ПЭТ)",
    "recyclable": true,
    "confidence": 95,
    "description": "Прозрачная пластиковая бутылка из-под напитка, пригодна для вторичной переработки."
}

Если на фото изображен человек, селфи, рука без предмета, мебель, животное или документ, установи "is_waste": false, "category": "other".
"""

def analyze_waste_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Отправляет изображение в OpenAI GPT Vision API (модель gpt-4o-mini)
    и возвращает структурированный JSON с классификацией отхода и флагом анти-фрода.
    """
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("YOUR_"):
        return {
            "success": False,
            "error": "Ключ OPENAI_API_KEY не установлен. Пожалуйста, укажите его в файле .env"
        }

    # Кодируем байты изображения в Base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Проверь фото на подлинность (не экран ли это) и классифицируй материал предмета для сортировки отходов."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 500
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Ошибка OpenAI API (HTTP {response.status_code}): {response.text[:250]}"
            }

        result = response.json()
        choices = result.get("choices", [])
        if not choices:
            return {
                "success": False,
                "error": "OpenAI API не вернул вариантов ответа."
            }

        raw_text = choices[0]["message"]["content"].strip()
        data = json.loads(raw_text)

        return {
            "success": True,
            "data": data
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Таймаут соединения с OpenAI API. Проверьте интернет-соединение."
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Нейросеть вернула ответ в некорректном формате JSON."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Внутренняя ошибка классификатора: {str(e)}"
        }
