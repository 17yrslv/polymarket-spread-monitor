import aiohttp
import asyncio

async def test_market_prices():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://gamma-api.polymarket.com/markets?limit=3') as resp:
            if resp.status == 200:
                markets = await resp.json()
                
                print('=== Market Price Structure ===\n')
                
                for i, market in enumerate(markets[:2], 1):
                    question = market.get('question', 'Unknown')
                    best_bid = float(market.get('bestBid', 0))
                    best_ask = float(market.get('bestAsk', 0))
                    
                    import json
                    outcome_prices = market.get('outcomePrices', '[]')
                    if isinstance(outcome_prices, str):
                        outcome_prices = json.loads(outcome_prices)
                    
                    yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0
                    no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0
                    
                    print(f'--- Market {i} ---')
                    print(f'Question: {question}')
                    print(f'bestBid (YES bid): {best_bid}')
                    print(f'bestAsk (YES ask): {best_ask}')
                    print(f'outcomePrices[0] (YES price): {yes_price}')
                    print(f'outcomePrices[1] (NO price): {no_price}')
                    print(f'1 - bestBid (NO ask): {1 - best_bid}')
                    print(f'1 - bestAsk (NO bid): {1 - best_ask}')
                    print()

asyncio.run(test_market_prices())
