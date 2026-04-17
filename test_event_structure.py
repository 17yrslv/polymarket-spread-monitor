import aiohttp
import asyncio
import json

async def test_event_structure():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://gamma-api.polymarket.com/markets?limit=500') as resp:
            if resp.status == 200:
                markets = await resp.json()
                
                # Find markets that are part of a group (event)
                grouped_markets = []
                for market in markets:
                    group_title = market.get('groupItemTitle')
                    if group_title and group_title != market.get('question'):
                        grouped_markets.append(market)
                        if len(grouped_markets) >= 3:
                            break
                
                if grouped_markets:
                    print('=== GROUPED MARKETS (Part of Events) ===\n')
                    for i, market in enumerate(grouped_markets, 1):
                        print(f'--- Market {i} ---')
                        print(f'Question: {market.get("question")}')
                        print(f'Slug: {market.get("slug")}')
                        print(f'Group Title: {market.get("groupItemTitle")}')
                        
                        # Check for event-related fields
                        events = market.get('events')
                        if events:
                            print(f'Events field: {type(events).__name__}')
                            if isinstance(events, list) and events:
                                print(f'First event: {events[0]}')
                        
                        print()
                else:
                    print('No grouped markets found')
            else:
                print(f'Status: {resp.status}')

asyncio.run(test_event_structure())
