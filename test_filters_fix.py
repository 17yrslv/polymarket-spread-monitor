#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест команды /filters
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from bot import Database

async def test_filters():
    """Тестирование get_filters"""
    
    print("=== Тест метода get_filters ===\n")
    
    # Инициализация
    db = Database()
    await db.init_db()
    
    # Тестовый user_id
    test_user_id = 123456789
    
    try:
        # Добавляем пользователя
        await db.add_user(test_user_id)
        print("Пользователь добавлен")
        
        # Добавляем несколько фильтров
        await db.set_filter(test_user_id, "spread_min", "2.5")
        print("Фильтр 1 добавлен: spread_min = 2.5")
        
        await db.set_filter(test_user_id, "volume_min", "100000")
        print("Фильтр 2 добавлен: volume_min = 100000")
        
        await db.set_filter(test_user_id, "trade_frequency_min", "10,5")
        print("Фильтр 3 добавлен: trade_frequency_min = 10,5")
        
        # Получаем фильтры
        filters = await db.get_filters(test_user_id)
        
        print(f"\nПолучено фильтров: {len(filters)}\n")
        
        # Проверяем структуру
        for filter_item in filters:
            print(f"Фильтр ID {filter_item['id']}:")
            print(f"  Тип: {filter_item['filter_type']}")
            print(f"  Значение: {filter_item['filter_value']}")
            print()
        
        # Удаляем один фильтр
        if filters:
            first_filter_id = filters[0]['id']
            success = await db.remove_filter(test_user_id, first_filter_id)
            print(f"Удаление фильтра ID {first_filter_id}: {'успешно' if success else 'ошибка'}")
        
        # Проверяем снова
        filters = await db.get_filters(test_user_id)
        print(f"\nОсталось фильтров: {len(filters)}")
        
        # Очищаем все фильтры
        for filter_item in filters:
            await db.remove_filter(test_user_id, filter_item["id"])
        
        filters = await db.get_filters(test_user_id)
        print(f"После очистки: {len(filters)} фильтров")
        
        print("\nТест завершен успешно!")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_filters())
