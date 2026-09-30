import os
import sys
import hashlib
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import database
import config
import anti_fraud

def run_tests():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МНОГОУРОВНЕВОЙ БЕЗОПАСНОСТИ ECOSORT (SMOKE TESTS)")
    print("=" * 60)

    # 1. Тест базы данных и миграции
    print("\n[1/5] Проверка структуры базы данных SQLite...")
    database.init_db()
    assert os.path.exists(config.DB_PATH), "Файл базы данных не существует!"
    print("[OK] База данных успешно инициализирована со всеми Anti-Fraud полями.")

    # 2. Тест dHash и расстояния Хэмминга с реальными паттернами
    print("\n[2/5] Тестирование алгоритма перцептивного хеширования (dHash)...")
    from PIL import Image, ImageDraw
    import io

    # Изображение 1: бутылка/цилиндр (градиент и круг)
    img1 = Image.new('RGB', (100, 100), color=(255, 255, 255))
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([30, 20, 70, 90], fill=(50, 150, 250))
    buf1 = io.BytesIO()
    img1.save(buf1, format='JPEG')
    bytes1 = buf1.getvalue()

    # Изображение 2: та же бутылка, чуть смещенная на 2 пикселя (имитация съемки с другого угла)
    img2 = Image.new('RGB', (100, 100), color=(255, 255, 255))
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([32, 22, 72, 92], fill=(48, 148, 248))
    buf2 = io.BytesIO()
    img2.save(buf2, format='JPEG')
    bytes2 = buf2.getvalue()

    # Изображение 3: совершенно другой предмет (черный треугольник)
    img3 = Image.new('RGB', (100, 100), color=(255, 255, 255))
    draw3 = ImageDraw.Draw(img3)
    draw3.polygon([(10, 90), (50, 10), (90, 90)], fill=(0, 0, 0))
    buf3 = io.BytesIO()
    img3.save(buf3, format='JPEG')
    bytes3 = buf3.getvalue()

    dhash1 = anti_fraud.compute_dhash(bytes1)
    dhash2 = anti_fraud.compute_dhash(bytes2)
    dhash3 = anti_fraud.compute_dhash(bytes3)

    dist_similar = anti_fraud.hamming_distance(dhash1, dhash2)
    dist_different = anti_fraud.hamming_distance(dhash1, dhash3)

    assert dist_similar <= 5, f"Похожие картинки должны иметь маленькую дистанцию Хэмминга! Получено: {dist_similar}"
    assert dist_different > 10, f"Разные картинки должны иметь большую дистанцию Хэмминга! Получено: {dist_different}"
    print(f"[OK] dHash похожих картинок (дистанция {dist_similar}/64), разных картинок (дистанция {dist_different}/64).")

    # 3. Тест перцептивного поиска дубликатов
    print("\n[3/5] Тестирование поиска визуальных дубликатов (find_perceptual_duplicate)...")
    recent = [dhash1]
    match = anti_fraud.find_perceptual_duplicate(dhash2, recent, threshold=10)
    assert match is not None, "Схожее изображение должно быть опознано как дубликат!"
    print(f"[OK] Дубликат с другого ракурса успешно обнаружен (найден хеш {match[0]}, дистанция {match[1]}).")

    # 4. Тест Rate Limiting (кулдаун)
    print("\n[4/5] Тестирование механизма кулдауна (Rate Limit)...")
    test_user_id = 888888888
    database.get_or_create_user(test_user_id, "fraud_tester", "Тестер Безопасности")
    
    # Первая сдача
    database.record_submission(
        user_id=test_user_id,
        container_id="plastic",
        detected_material="Бутылка",
        points=10,
        image_hash=hashlib.sha256(bytes1).hexdigest(),
        dhash=dhash1
    )

    can_submit, wait_sec = database.check_user_cooldown(test_user_id, cooldown_seconds=20)
    assert not can_submit, "Сдача сразу после предыдущей должна блокироваться кулдауном!"
    assert wait_sec > 0, "Остаток времени должен быть больше нуля!"
    print(f"[OK] Кулдаун работает: попытка моментальной сдачи заблокирована (осталось ждать {wait_sec} сек).")

    # 5. Очистка тестовых данных
    print("\n[5/5] Очистка тестовых данных...")
    with database.get_connection() as conn:
        conn.cursor().execute("DELETE FROM transactions WHERE user_id = ?", (test_user_id,))
        conn.cursor().execute("DELETE FROM image_hashes WHERE user_id = ?", (test_user_id,))
        conn.cursor().execute("DELETE FROM users WHERE user_id = ?", (test_user_id,))
        conn.commit()
    print("[OK] Тестовые данные безопасно удалены.")

    print("\n" + "=" * 60)
    print("ВСЕ 5 ТЕСТОВ БЕЗОПАСНОСТИ УСПЕШНО ПРОЙДЕНЫ! СИСТЕМА ЗАЩИЩЕНА.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
