import time
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация и миграция таблиц базы данных SQLite"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Пользователи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                points INTEGER DEFAULT 0,
                items_count INTEGER DEFAULT 0,
                last_submission_time REAL DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # История успешных сдач отходов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                container_id TEXT,
                detected_material TEXT,
                points_earned INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Реестр хешей фотографий (SHA-256 и dHash перцептивный хеш)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_hashes (
                image_hash TEXT PRIMARY KEY,
                dhash TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Миграция: добавляем колонки, если база уже существовала ранее
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_submission_time REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

        try:
            cursor.execute("ALTER TABLE image_hashes ADD COLUMN dhash TEXT")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

        conn.commit()

def get_or_create_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute(
                "INSERT INTO users (user_id, username, first_name, points, items_count, last_submission_time) VALUES (?, ?, ?, 0, 0, 0)",
                (user_id, username or "", first_name or "Пользователь")
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
        return dict(row)

def check_user_cooldown(user_id: int, cooldown_seconds: int = 20) -> Tuple[bool, int]:
    """
    Проверяет, прошло ли достаточно времени с момента прошлой сдачи отхода.
    Возвращает (can_submit: bool, remaining_seconds: int).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_submission_time FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or not row["last_submission_time"]:
            return (True, 0)
            
        last_time = row["last_submission_time"]
        elapsed = time.time() - last_time
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed) + 1
            return (False, remaining)
            
        return (True, 0)

def is_sha256_exists(image_hash: str) -> bool:
    """Проверка точного совпадения байт-в-байт по SHA-256"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM image_hashes WHERE image_hash = ?", (image_hash,))
        return cursor.fetchone() is not None

def get_recent_dhashes(limit: int = 300) -> List[str]:
    """Получает пул последних перцептивных хешей dHash для поиска схожих фото"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT dhash FROM image_hashes WHERE dhash IS NOT NULL AND dhash != '' ORDER BY created_at DESC LIMIT ?", (limit,))
        return [row["dhash"] for row in cursor.fetchall()]

def record_submission(user_id: int, container_id: str, detected_material: str, points: int, image_hash: str, dhash: str = "") -> int:
    """Запись успешной сдачи, начисление очков, фиксация хешей и обновление времени сдачи"""
    now = time.time()
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Фиксируем точный и перцептивный хеши
        cursor.execute(
            "INSERT INTO image_hashes (image_hash, dhash, user_id) VALUES (?, ?, ?)",
            (image_hash, dhash, user_id)
        )
        
        # 2. Фиксируем транзакцию сдачи
        cursor.execute(
            "INSERT INTO transactions (user_id, container_id, detected_material, points_earned) VALUES (?, ?, ?, ?)",
            (user_id, container_id, detected_material, points)
        )
        
        # 3. Обновляем баланс, счетчик предметов и время последней активности
        cursor.execute(
            "UPDATE users SET points = points + ?, items_count = items_count + 1, last_submission_time = ? WHERE user_id = ?",
            (points, now, user_id)
        )
        
        conn.commit()
        
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()["points"]
        return new_balance

def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Получение статистики пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return {"points": 0, "items_count": 0, "categories": {}}
            
        cursor.execute("""
            SELECT container_id, COUNT(*) as count, SUM(points_earned) as total_points
            FROM transactions
            WHERE user_id = ?
            GROUP BY container_id
        """, (user_id,))
        
        categories = {}
        for row in cursor.fetchall():
            categories[row["container_id"]] = {
                "count": row["count"],
                "points": row["total_points"]
            }
            
        return {
            "points": user_row["points"],
            "items_count": user_row["items_count"],
            "registered_at": user_row["registered_at"],
            "categories": categories
        }

def get_leaderboard(limit: int = 5) -> List[Dict[str, Any]]:
    """Получение топа пользователей"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT first_name, username, points, items_count
            FROM users
            ORDER BY points DESC, items_count DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
