import sqlite3
import os
import cv2
import threading
from config import DATABASE

class DatabaseManager:
    def __init__(self, database):
        self.database = database
        self.lock = threading.Lock()
        self.create_tables()  # Создаем таблицы при инициализации

    def _get_connection(self):
        """Создает новое потокобезопасное соединение"""
        return sqlite3.connect(self.database, check_same_thread=False)

    

    def create_tables(self):
        with self.lock, self._get_connection() as conn:
            # Удаляем старые таблицы
            conn.execute("DROP TABLE IF EXISTS users")
            conn.execute("DROP TABLE IF EXISTS prizes")
            
            # Создаем новые таблицы с правильными полями
            conn.execute('''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    points INTEGER DEFAULT 0
                )
            ''')
            conn.execute('''
                CREATE TABLE prizes (
                    prize_id INTEGER PRIMARY KEY,
                    image TEXT,
                    claims INTEGER DEFAULT 0
                )
            ''')
            conn.commit()

    def user_exists(self, user_id):
        """Проверяет существование пользователя в базе"""
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
            return cursor.fetchone() is not None

    def add_user(self, user_id, username):
        """Добавляет пользователя с проверкой структуры"""
        with self.lock, self._get_connection() as conn:
            conn.execute('''
                INSERT OR IGNORE INTO users (user_id, username)
                VALUES (?, ?)
            ''', (user_id, username))
            conn.commit()

    def get_active_users(self):
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            return [row[0] for row in cursor.fetchall()]

    # ================== Prize Methods ==================
    def add_prize(self, image_path):
        with self.lock, self._get_connection() as conn:
            conn.execute('''
                INSERT INTO prizes (image)
                VALUES (?)
            ''', (image_path,))
            conn.commit()

    def get_available_prize(self):
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT prize_id, image FROM prizes
                WHERE claims < 3
                ORDER BY RANDOM()
                LIMIT 1
            ''')
            return cursor.fetchone()

    def get_prize_img(self, prize_id):
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT image FROM prizes
                WHERE prize_id=?
            ''', (prize_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def get_prize_claim_count(self, prize_id):
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT claims FROM prizes
                WHERE prize_id=?
            ''', (prize_id,))
            result = cursor.fetchone()
            return result[0] if result else 0

    def claim_prize(self, prize_id, user_id):
        with self.lock, self._get_connection() as conn:
            try:
                # Обновляем счетчик приза
                conn.execute('''
                    UPDATE prizes
                    SET claims = claims + 1
                    WHERE prize_id=?
                ''', (prize_id,))
                
                # Обновляем очки пользователя
                conn.execute('''
                    UPDATE users
                    SET points = points + 1
                    WHERE user_id=?
                ''', (user_id,))
                
                conn.commit()
                return True
            except sqlite3.Error:
                conn.rollback()
                return False

    def reset_prize_claims(self, prize_id):
        with self.lock, self._get_connection() as conn:
            conn.execute('''
                UPDATE prizes
                SET claims = 0
                WHERE prize_id=?
            ''', (prize_id,))
            conn.commit()

    # ================== Rating Methods ==================
    def get_users_rating(self):
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT username, points
                FROM users
                ORDER BY points DESC
                LIMIT 10
            ''')
            return cursor.fetchall()

def hide_img(img_name):
    """Пикселизация изображения"""
    try:
        image = cv2.imread(f'img/{img_name}')
        if image is None:
            raise FileNotFoundError(f"Image {img_name} not found")
        
        # Пикселизация
        small = cv2.resize(image, (30, 30), interpolation=cv2.INTER_NEAREST)
        pixelated = cv2.resize(small, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
        
        # Сохранение
        os.makedirs('hidden_img', exist_ok=True)
        cv2.imwrite(f'hidden_img/{img_name}', pixelated)
        
    except Exception as e:
        print(f"Image processing error: {str(e)}")

if __name__ == '__main__':
    # Инициализация тестовых данных
    db = DatabaseManager(DATABASE)
    
    # Добавление тестовых призов
    if os.path.exists('img'):
        for img in os.listdir('img'):
            db.add_prize(img)
