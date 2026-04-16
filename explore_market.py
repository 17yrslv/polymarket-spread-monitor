import aiohttp
import asyncio
import json

async def explore_market_structure():
    """Исследуем структуру данных рынка для поиска полей с категориями"""
    async with aiohttp.ClientSession() as session:
        print("=== Исследование структуры рынка Polymarket ===\n")
        
        # Получаем несколько рынков
        async with session.get('https://gamma-api.polymarket.com/markets?limit=10') as resp:
            markets = await resp.json()
            
            if isinstance(markets, list) and markets:
                print(f"Получено {len(markets)} рынков\n")
                
                # Собираем все уникальные ключи из всех рынков
                all_keys = set()
                for market in markets:
                    all_keys.update(market.keys())
                
                print(f"Все найденные поля ({len(all_keys)}):")
                for key in sorted(all_keys):
                    print(f"  - {key}")
                print()
                
                # Ищем потенциальные поля с категориями/тегами
                category_related_keys = [
                    'category', 'categories', 'tag', 'tags', 'group', 'groupItemTitle', 
                    'section', 'sections', 'theme', 'themes', 'topic', 'topics'
                ]
                
                print("Потенциальные поля с категориями:")
                found_category_fields = []
                for key in all_keys:
                    if any(cat_key in key.lower() for cat_key in category_related_keys):
                        found_category_fields.append(key)
                        print(f"  - {key}")
                print()
                
                # Покажем значения этих полей для первых нескольких рынков
                if found_category_fields:
                    print("Значения полей с категориями для первых 3 рынков:")
                    for i, market in enumerate(markets[:3]):
                        print(f"\n  Рынок {i+1}: {market.get('question', 'Unknown')[:50]}...")
                        for field in found_category_fields:
                            value = market.get(field)
                            if value is not None:
                                if isinstance(value, str) and len(value) > 100:
                                    print(f"    {field}: {value[:100]}...")
                                else:
                                    print(f"    {field}: {value}")
                else:
                    print("Поля с категориями не найдены в явном виде")
                    print("\nПокажем несколько полных записей для ручного анализа:")
                    for i, market in enumerate(markets[:2]):
                        print(f"\n=== Рынок {i+1} ===")
                        print(f"Question: {market.get('question')}")
                        print(f"Slug: {market.get('slug')}")
                        # Покажем несколько интересных полей
                        interesting_fields = ['outcomePrices', 'volume', 'liquidity', 'bestBid', 'bestAsk', 
                                            'createdAt', 'endDate', 'closed', 'archived']
                        for field in interesting_fields:
                            if field in market:
                                print(f"{field}: {market[field]}")
                        
                        # Покажем все поля со значениями
                        print("\nВсе поля:")
                        for key, value in sorted(market.items()):
                            if isinstance(value, (str, int, float, bool)) or value is None:
                                print(f"  {key}: {value}")
                            elif isinstance(value, list):
                                print(f"  {key}: [{len(value)} items] {value[:3] if len(value) > 3 else value}")
                            elif isinstance(value, dict):
                                print(f"  {key}: {{...}} ({len(value)} keys)")
                            else:
                                print(f"  {key}: <{type(value).__name__}>")

asyncio.run(explore_market_structure())
