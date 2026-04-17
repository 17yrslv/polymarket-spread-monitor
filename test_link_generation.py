import aiohttp
import asyncio
import json

async def test_link_generation():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://gamma-api.polymarket.com/markets?limit=100') as resp:
            if resp.status == 200:
                markets = await resp.json()
                
                print('=== Testing Link Generation ===\n')
                
                # Test 1: Market with event (grouped market)
                grouped_market = None
                for market in markets:
                    events = market.get('events', [])
                    if isinstance(events, str):
                        events = json.loads(events)
                    if events and len(events) > 0:
                        grouped_market = market
                        break
                
                if grouped_market:
                    print('--- Test 1: Grouped Market (Part of Event) ---')
                    slug = grouped_market.get('slug', '')
                    events = grouped_market.get('events', [])
                    if isinstance(events, str):
                        events = json.loads(events)
                    
                    if events and len(events) > 0 and slug:
                        event_slug = events[0].get('slug', '')
                        market_url = f"https://polymarket.com/event/{event_slug}/{slug}"
                    elif slug:
                        market_url = f"https://polymarket.com/event/{slug}"
                    else:
                        market_url = ""
                    
                    print(f'Question: {grouped_market.get("question")}')
                    print(f'Event Slug: {events[0].get("slug") if events else "N/A"}')
                    print(f'Market Slug: {slug}')
                    print(f'Generated URL: {market_url}')
                    print()
                
                # Test 2: Standalone market (no event)
                standalone_market = None
                for market in markets:
                    events = market.get('events', [])
                    if isinstance(events, str):
                        events = json.loads(events)
                    if not events or len(events) == 0:
                        standalone_market = market
                        break
                
                if standalone_market:
                    print('--- Test 2: Standalone Market (No Event) ---')
                    slug = standalone_market.get('slug', '')
                    events = standalone_market.get('events', [])
                    if isinstance(events, str):
                        events = json.loads(events)
                    
                    if events and len(events) > 0 and slug:
                        event_slug = events[0].get('slug', '')
                        market_url = f"https://polymarket.com/event/{event_slug}/{slug}"
                    elif slug:
                        market_url = f"https://polymarket.com/event/{slug}"
                    else:
                        market_url = ""
                    
                    print(f'Question: {standalone_market.get("question")}')
                    print(f'Event Slug: N/A')
                    print(f'Market Slug: {slug}')
                    print(f'Generated URL: {market_url}')
                    print()
                
                print('=== Summary ===')
                print('✓ Grouped markets: event/{event_slug}/{market_slug}')
                print('✓ Standalone markets: event/{market_slug}')
            else:
                print(f'Status: {resp.status}')

asyncio.run(test_link_generation())
