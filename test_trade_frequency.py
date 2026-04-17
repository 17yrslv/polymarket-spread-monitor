#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест фильтра частоты сделок
"""

import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
from dotenv import load_dotenv
import os

load_dotenv()

# Импортируем классы из bot.py
import sys
sys.path.insert(0, os.path.dirname(__file__))

from bot import PolymarketAPI, Database

PROXY_URL = os.getenv("PROXY_URL", "")

async def test_trade_frequency():
    """Тестирование получения частоты сделок"""
    
    print("=== Тест фильтра частоты сделок ===\n")
    
    # Инициализация
    db = Database()
    await db.init_db()
    
    connector = ProxyConnector.from_url(PROXY_URL) if PROXY_URL else None
    http_session = aiohttp.ClientSession(connector=connector)
    api = PolymarketAPI(http_session)
    
    try:
        # Получаем несколько активных рынков для теста
        print("Загрузка рынков...")
        markets = await api.get_all_markets(use_cache=False)
        
        if not markets:
            print("Не удалось загрузить рынки")
            return
        
        print(f"Загружено {len(markets)} рынков\n")
        
        # Тестируем на первых 5 рынках
        test_markets = markets[:5]
        
        for i, market in enumerate(test_markets, 1):
            market_name = market.get("question", "Unknown")
            condition_id = market.get("conditionId", "")
            slug = market.get("slug", "")
            
            if not condition_id:
                print(f"{i}. {market_name[:50]}... - нет conditionId")
                continue
            
            print(f"{i}. {market_name[:60]}...")
            print(f"   Slug: {slug}")
            print(f"   Condition ID: {condition_id}")
            
            # Проверяем частоту сделок за 5 минут
            period_minutes = 5
            trade_count = await api.get_trade_frequency(condition_id, period_minutes, db)
            
            print(f"   Сделок за последние {period_minutes} минут: {trade_count}")
            
            # Проверяем кэш
            cached_count = await db.get_trade_frequency_cache(condition_id, period_minutes)
            if cached_count is not None:
                print(f"   Кэш работает: {cached_count}")
            
            print()
        
        print("\nТест завершен успешно!")
        print("\nКак использовать новый фильтр:")
        print("   /set_filter trade_frequency_min 10 5")
        print("   (минимум 10 сделок за 5 минут)")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await http_session.close()

if __name__ == "__main__":
    asyncio.run(test_trade_frequency())
