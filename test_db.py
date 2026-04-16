import aiosqlite
import asyncio
from datetime import datetime, timedelta

async def test_database():
    """Тестируем новую структуру БД"""
    db_path = "test_bot.db"
    
    # Удаляем старую тестовую БД если существует
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Создаем БД и инициализируем таблицы
    async with aiosqlite.connect(db_path) as db:
        # Таблицы пользователей и рынков (существующие)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                market_slug TEXT NOT NULL,
                market_name TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, market_slug)
            )
        """)
        
        # НОВЫЕ ТАБЛИЦЫ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS auto_scan_settings (
                user_id INTEGER PRIMARY KEY,
                is_enabled INTEGER DEFAULT 0,
                scan_mode TEXT DEFAULT 'all',
                scan_interval INTEGER DEFAULT 60,
                dedup_hours INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, category)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                market_slug TEXT NOT NULL,
                spread_value REAL NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_history 
            ON notification_history(user_id, market_slug, sent_at)
        """)
        
        await db.commit()
        
        # Тестируем вставку и выборку
        user_id = 12345
        
        # Добавляем настройки автосканирования
        await db.execute(
            "INSERT INTO auto_scan_settings (user_id, is_enabled, scan_mode, scan_interval, dedup_hours) VALUES (?, ?, ?, ?, ?)",
            (user_id, 1, 'categories', 60, 2)
        )
        
        # Добавляем категории
        await db.execute(
            "INSERT INTO scan_categories (user_id, category) VALUES (?, ?)",
            (user_id, 'Politics')
        )
        await db.execute(
            "INSERT INTO scan_categories (user_id, category) VALUES (?, ?)",
            (user_id, 'Crypto')
        )
        
        # Добавляем запись в историю уведомлений
        await db.execute(
            "INSERT INTO notification_history (user_id, market_slug, spread_value) VALUES (?, ?, ?)",
            (user_id, 'test-market-slug', 2.5)
        )
        
        await db.commit()
        
        # Читаем данные
        async with db.execute("SELECT * FROM auto_scan_settings WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            print(f"Auto scan settings: {row}")
        
        async with db.execute("SELECT * FROM scan_categories WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            print(f"Scan categories: {rows}")
        
        async with db.execute("SELECT * FROM notification_history WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            print(f"Notification history: {rows}")
        
        # Тестируем очистку старых уведомлений
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        await db.execute(
            "INSERT INTO notification_history (user_id, market_slug, spread_value, sent_at) VALUES (?, ?, ?, ?)",
            (user_id, 'old-market', 1.0, old_date)
        )
        await db.commit()
        
        async with db.execute("SELECT COUNT(*) FROM notification_history WHERE user_id = ?", (user_id,)) as cursor:
            count_before = (await cursor.fetchone())[0]
            print(f"Notifications before cleanup: {count_before}")
        
        # Очищаем уведомления старше 7 дней
        cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
        await db.execute(
            "DELETE FROM notification_history WHERE sent_at < ?",
            (cutoff_date,)
        )
        await db.commit()
        
        async with db.execute("SELECT COUNT(*) FROM notification_history WHERE user_id = ?", (user_id,)) as cursor:
            count_after = (await cursor.fetchone())[0]
            print(f"Notifications after cleanup: {count_after}")
    
    # Удаляем тестовую БД
    os.remove(db_path)
    print("Database test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_database())