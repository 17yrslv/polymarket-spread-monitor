import aiohttp
import asyncio

async def test_spread_calculation():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://gamma-api.polymarket.com/markets?limit=5') as resp:
            if resp.status == 200:
                markets = await resp.json()
                
                print('=== Testing Spread Calculation ===\n')
                
                for i, market in enumerate(markets[:3], 1):
                    question = market.get('question', 'Unknown')
                    best_bid = float(market.get('bestBid', 0))
                    best_ask = float(market.get('bestAsk', 0))
                    
                    if best_bid > 0 and best_ask > 0:
                        spread = ((best_ask / best_bid) - 1) * 100
                        
                        print(f'--- Market {i} ---')
                        print(f'Question: {question}')
                        print(f'Best Bid: {best_bid}')
                        print(f'Best Ask: {best_ask}')
                        print(f'Spread: {spread:.2f}%')
                        print(f'Formula: (({best_ask}/{best_bid})-1)*100 = {spread:.2f}%')
                        print()
            else:
                print(f'Status: {resp.status}')

asyncio.run(test_spread_calculation())
