import io
from PIL import Image
from typing import List, Optional, Tuple

def compute_dhash(image_bytes: bytes, hash_size: int = 8) -> str:
    """
    Вычисляет 64-битный перцептивный хеш разницы (dHash) для изображения.
    Устойчив к масштабированию, легким поворотам, изменению освещения и ракурса.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # 1. Переводим в градации серого
        image = image.convert('L')
        # 2. Масштабируем до (hash_size + 1, hash_size), например 9x8
        image = image.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        
        pixels = list(image.getdata())
        
        # 3. Сравниваем соседние пиксели по горизонтали
        difference = []
        width = hash_size + 1
        for row in range(hash_size):
            for col in range(hash_size):
                pixel_left = pixels[row * width + col]
                pixel_right = pixels[row * width + col + 1]
                difference.append(pixel_left > pixel_right)
                
        # 4. Преобразуем битовый массив в шестнадцатеричную строку (16 символов для 64 бит)
        decimal_val = 0
        for bit in difference:
            decimal_val = (decimal_val << 1) | int(bit)
            
        hex_hash = f"{decimal_val:016x}"
        return hex_hash
    except Exception:
        return ""

def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Вычисляет расстояние Хэмминга (число различающихся бит) между двумя шестнадцатеричными хешами.
    Чем меньше расстояние, тем больше визуальное сходство изображений.
    Диапазон: 0 (полная копия) до 64 (абсолютно разные).
    """
    try:
        if not hash1 or not hash2:
            return 64
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        xor_result = val1 ^ val2
        return bin(xor_result).count('1')
    except Exception:
        return 64

def find_perceptual_duplicate(new_hash: str, existing_hashes: List[str], threshold: int = 10) -> Optional[Tuple[str, int]]:
    """
    Ищет в списке ранее сохраненных хешей дубликат с расстоянием Хэмминга <= threshold.
    По умолчанию threshold = 10 бит различий из 64 (~85% визуального совпадения).
    Возвращает (найденный_хеш, расстояние) или None.
    """
    if not new_hash:
        return None

    for existing_hash in existing_hashes:
        if not existing_hash:
            continue
        dist = hamming_distance(new_hash, existing_hash)
        if dist <= threshold:
            return (existing_hash, dist)
            
    return None
