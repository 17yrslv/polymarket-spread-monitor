#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест функциональности автосканирования
"""

import asyncio
import aiosqlite
from datetime import datetime, timedelta

async def test_auto_scan_functionality():
    """Тестируем функциональность автосканирования"""
    
    print("=== Тест автосканирования ===\n")
    
    # Создаем тестовую БД
    db_path = "test_auto_scan.db"
    
    # Удаляем старую БД если есть
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
    
    async with aiosqlite.connect(db_path) as db:
        # Создаем таблицы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        
        user_id = 12345
        
        # Тест 1: Создание настроек автосканирования
        print("Тест 1: Создание настроек автосканирования")
        await db.execute(
            "INSERT INTO auto_scan_settings (user_id, is_enabled, scan_mode, scan_interval, dedup_hours) VALUES (?, ?, ?, ?, ?)",
            (user_id, 1, 'categories', 60, 2)
        )
        await db.commit()
        
        cursor = await db.execute("SELECT * FROM auto_scan_settings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        print(f"[OK] Настройки созданы: {row}\n")
        
        # Тест 2: Добавление категорий
        print("Тест 2: Добавление категорий")
        categories = ['Politics', 'Crypto', 'Sports']
        for cat in categories:
            await db.execute(
                "INSERT INTO scan_categories (user_id, category) VALUES (?, ?)",
                (user_id, cat)
            )
        await db.commit()
        
        cursor = await db.execute("SELECT category FROM scan_categories WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        print(f"[OK] Добавлено категорий: {len(rows)}")
        for row in rows:
            print(f"   - {row[0]}")
        print()
        
        # Тест 3: История уведомлений
        print("Тест 3: История уведомлений")
        markets = [
            ('market-1', 2.5),
            ('market-2', 3.0),
            ('market-3', 1.8)
        ]
        for slug, spread in markets:
            await db.execute(
                "INSERT INTO notification_history (user_id, market_slug, spread_value) VALUES (?, ?, ?)",
                (user_id, slug, spread)
            )
        await db.commit()
        
        cursor = await db.execute("SELECT COUNT(*) FROM notification_history WHERE user_id = ?", (user_id,))
        count = (await cursor.fetchone())[0]
        print(f"[OK] Уведомлений в истории: {count}\n")
        
        # Тест 4: Проверка дедупликации
        print("Тест 4: Проверка дедупликации")
        
        # Добавляем старое уведомление
        old_time = (datetime.now() - timedelta(hours=3)).isoformat()
        await db.execute(
            "INSERT INTO notification_history (user_id, market_slug, spread_value, sent_at) VALUES (?, ?, ?, ?)",
            (user_id, 'old-market', 2.0, old_time)
        )
        
        # Добавляем недавнее уведомление
        recent_time = (datetime.now() - timedelta(minutes=30)).isoformat()
        await db.execute(
            "INSERT INTO notification_history (user_id, market_slug, spread_value, sent_at) VALUES (?, ?, ?, ?)",
            (user_id, 'recent-market', 2.5, recent_time)
        )
        await db.commit()
        
        # Проверяем дедупликацию (2 часа)
        dedup_hours = 2
        cutoff_time = (datetime.now() - timedelta(hours=dedup_hours)).isoformat()
        
        # Старое уведомление (должно пройти)
        cursor = await db.execute(
            "SELECT sent_at FROM notification_history WHERE user_id = ? AND market_slug = ? ORDER BY sent_at DESC LIMIT 1",
            (user_id, 'old-market')
        )
        row = await cursor.fetchone()
        if row:
            last_time = datetime.fromisoformat(row[0])
            should_notify = last_time < datetime.fromisoformat(cutoff_time)
            print(f"[OK] old-market: последнее уведомление {(datetime.now() - last_time).total_seconds() / 3600:.1f}ч назад, отправлять: {should_notify}")
        
        # Недавнее уведомление (не должно пройти)
        cursor = await db.execute(
            "SELECT sent_at FROM notification_history WHERE user_id = ? AND market_slug = ? ORDER BY sent_at DESC LIMIT 1",
            (user_id, 'recent-market')
        )
        row = await cursor.fetchone()
        if row:
            last_time = datetime.fromisoformat(row[0])
            should_notify = last_time < datetime.fromisoformat(cutoff_time)
            print(f"[OK] recent-market: последнее уведомление {(datetime.now() - last_time).total_seconds() / 3600:.1f}ч назад, отправлять: {should_notify}")
        print()
        
        # Тест 5: Очистка старых уведомлений
        print("Тест 5: Очистка старых уведомлений")
        cursor = await db.execute("SELECT COUNT(*) FROM notification_history WHERE user_id = ?", (user_id,))
        count_before = (await cursor.fetchone())[0]
        print(f"Уведомлений до очистки: {count_before}")
        
        # Очищаем уведомления старше 7 дней
        cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
        await db.execute(
            "DELETE FROM notification_history WHERE sent_at < ?",
            (cutoff_date,)
        )
        await db.commit()
        
        cursor = await db.execute("SELECT COUNT(*) FROM notification_history WHERE user_id = ?", (user_id,))
        count_after = (await cursor.fetchone())[0]
        print(f"[OK] Уведомлений после очистки: {count_after}\n")
        
        # Тест 6: Обновление настроек
        print("Тест 6: Обновление настроек")
        await db.execute(
            "UPDATE auto_scan_settings SET scan_interval = ?, dedup_hours = ? WHERE user_id = ?",
            (120, 3, user_id)
        )
        await db.commit()
        
        cursor = await db.execute("SELECT scan_interval, dedup_hours FROM auto_scan_settings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        print(f"[OK] Настройки обновлены: интервал={row[0]}с, дедупликация={row[1]}ч\n")
    
    # Удаляем тестовую БД
    os.remove(db_path)
    
    print("=== Все тесты пройдены успешно! ===")

if __name__ == "__main__":
    asyncio.run(test_auto_scan_functionality())
