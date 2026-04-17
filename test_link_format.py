import aiohttp
import asyncio
import json

async def test_link_format():
    async with aiohttp.ClientSession() as session:
        # Search for markets with multiple outcomes
        async with session.get('https://gamma-api.polymarket.com/markets?limit=500') as resp:
            if resp.status == 200:
                markets = await resp.json()
                
                # Find a market with more than 2 outcomes
                multi_outcome_market = None
                for market in markets:
                    outcomes = market.get('outcomes')
                    if isinstance(outcomes, str):
                        outcomes = json.loads(outcomes)
                    if outcomes and len(outcomes) > 2:
                        multi_outcome_market = market
                        break
                
                if multi_outcome_market:
                    print('=== MULTI-OUTCOME MARKET FOUND ===')
                    market = multi_outcome_market
                else:
                    print('=== NO MULTI-OUTCOME MARKET FOUND, USING BINARY MARKET ===')
                    market = markets[0]
                
                print(f'Market: {market.get("question")}')
                print(f'Slug: {market.get("slug")}')
                print()
                
                # Check outcomes
                outcomes = market.get('outcomes')
                if outcomes:
                    print('=== OUTCOMES ===')
                    if isinstance(outcomes, str):
                        outcomes = json.loads(outcomes)
                    print(f'Count: {len(outcomes)}')
                    print(f'Values: {outcomes}')
                    print()
                
                # Check for tokens field
                tokens = market.get('tokens')
                if tokens:
                    print('=== TOKENS ===')
                    if isinstance(tokens, str):
                        tokens = json.loads(tokens)
                    print(json.dumps(tokens[:2] if len(tokens) > 2 else tokens, indent=2))
                    print()
                
                # Print all fields
                print('=== ALL FIELDS ===')
                for key in sorted(market.keys()):
                    value = market[key]
                    if isinstance(value, (str, int, float, bool)):
                        print(f'{key}: {value}')
                    else:
                        print(f'{key}: {type(value).__name__}')
            else:
                print(f'Status: {resp.status}')

asyncio.run(test_link_format())
