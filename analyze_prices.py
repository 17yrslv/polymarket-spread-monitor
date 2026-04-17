import aiohttp
import asyncio
import json

async def analyze_market_prices():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://gamma-api.polymarket.com/markets?limit=3') as resp:
            markets = await resp.json()
            
            for market in markets:
                print('=' * 70)
                print(f'Market: {market.get("question")}')
                
                # Market level data
                best_bid = market.get('bestBid')
                best_ask = market.get('bestAsk')
                outcome_prices_str = market.get('outcomePrices')
                
                print(f'bestBid: {best_bid}')
                print(f'bestAsk: {best_ask}')
                
                if outcome_prices_str:
                    outcome_prices = json.loads(outcome_prices_str)
                    print(f'outcomePrices: {outcome_prices}')
                    
                    # Calculate spread using market level bid/ask
                    if best_bid and best_ask and best_bid > 0:
                        spread = ((best_ask / best_bid) - 1) * 100
                        print(f'Spread (market level): {spread:.2f}%')
                    
                    # Check if bestBid/bestAsk match YES price
                    if outcome_prices and len(outcome_prices) > 0:
                        yes_price = float(outcome_prices[0])
                        print(f'YES price: {yes_price}')
                        
                        # Check if market bid/ask are around YES price
                        if best_bid and best_ask:
                            avg_market_price = (best_bid + best_ask) / 2
                            print(f'Avg market price: {avg_market_price:.3f}')
                            print(f'Difference from YES: {abs(avg_market_price - yes_price):.3f}')
                
                print()

asyncio.run(analyze_market_prices())
