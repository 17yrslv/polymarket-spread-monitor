import aiohttp
import asyncio

async def explore_categories():
    """Исследуем категории/группы в данных рынка"""
    async with aiohttp.ClientSession() as session:
        print("=== Исследование категорий в Polymarket ===\n")
        
        # Получаем больше рынков для лучшего анализа
        async with session.get('https://gamma-api.polymarket.com/markets?limit=50') as resp:
            markets = await resp.json()
            
            if isinstance(markets, list) and markets:
                print(f"Получено {len(markets)} рынков\n")
                
                # Собираем уникальные значения groupItemTitle
                group_titles = set()
                for market in markets:
                    title = market.get('groupItemTitle')
                    if title:
                        group_titles.add(title)
                
                print(f"Уникальные значения groupItemTitle ({len(group_titles)}):")
                for title in sorted(group_titles)[:20]:  # Покажем первые 20
                    print(f"  - {title}")
                
                if len(group_titles) > 20:
                    print(f"  ... и ещё {len(group_titles) - 20}")
                print()
                
                # Посчитаем распределение по группам
                group_counts = {}
                for market in markets:
                    title = market.get('groupItemTitle', 'Без группы')
                    group_counts[title] = group_counts.get(title, 0) + 1
                
                print("Топ-10 групп по количеству рынков:")
                sorted_groups = sorted(group_counts.items(), key=lambda x: x[1], reverse=True)
                for group, count in sorted_groups[:10]:
                    print(f"  {group}: {count} рынков")
                print()
                
                # Посмотрим на несколько примеров из разных групп
                print("Примеры рынков из разных групп:")
                shown_groups = set()
                for market in markets:
                    title = market.get('groupItemTitle')
                    if title and title not in shown_groups:
                        print(f"\nГруппа: {title}")
                        print(f"  Вопрос: {market.get('question')}")
                        print(f"  Slug: {market.get('slug')}")
                        print(f"  Объем: ${float(market.get('volume', 0)):,.0f}")
                        shown_groups.add(title)
                        if len(shown_groups) >= 5:
                            break

asyncio.run(explore_categories())
