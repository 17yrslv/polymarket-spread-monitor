#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест исправления timestamp
"""

import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
from dotenv import load_dotenv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

from bot import PolymarketAPI, Database

PROXY_URL = os.getenv("PROXY_URL", "")

async def test_timestamp_fix():
    """Тестирование исправления timestamp"""
    
    print("=== Тест исправления timestamp ===\n")
    
    # Инициализация
    db = Database()
    await db.init_db()
    
    connector = ProxyConnector.from_url(PROXY_URL) if PROXY_URL else None
    http_session = aiohttp.ClientSession(connector=connector)
    api = PolymarketAPI(http_session)
    
    try:
        # Тестовый condition_id с активными сделками
        condition_id = "0x37ec4c6b57a18b16eed1241f6155ee7ff45bc1697d7848f15ac33d406e38ed00"
        market_name = "Will Michelle Bolsonaro win the 2026 Brazilian presidential election?"
        
        print(f"Рынок: {market_name}")
        print(f"Condition ID: {condition_id}\n")
        
        # Проверяем частоту сделок за разные периоды
        periods = [1, 5, 10]
        
        for period in periods:
            trade_count = await api.get_trade_frequency(condition_id, period, db)
            print(f"Сделок за последние {period} мин: {trade_count}")
        
        print("\nИсправление работает!")
        print("Теперь бот должен находить активные рынки.")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await http_session.close()

if __name__ == "__main__":
    asyncio.run(test_timestamp_fix())
