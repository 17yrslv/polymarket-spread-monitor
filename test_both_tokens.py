import aiohttp
import asyncio
import json

async def test_both_tokens():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://gamma-api.polymarket.com/markets?limit=1') as resp:
            markets = await resp.json()
            market = markets[0]
            
            clob_ids = json.loads(market.get('clobTokenIds'))
            outcomes = json.loads(market.get('outcomes'))
            
            print(f'Market: {market.get("question")}')
            print(f'Market bestBid: {market.get("bestBid")}')
            print(f'Market bestAsk: {market.get("bestAsk")}\n')
            
            for i, (token_id, outcome) in enumerate(zip(clob_ids, outcomes)):
                print(f'=== {outcome} (Token {i}) ===')
                async with session.get(f'https://clob.polymarket.com/book?token_id={token_id}') as book_resp:
                    if book_resp.status == 200:
                        book = await book_resp.json()
                        bids = book.get('bids', [])
                        asks = book.get('asks', [])
                        
                        if bids and asks:
                            best_bid = float(bids[0]['price'])
                            best_ask = float(asks[0]['price'])
                            
                            if best_bid > 0:
                                spread = ((best_ask / best_bid) - 1) * 100
                                print(f'Best Bid: {best_bid}')
                                print(f'Best Ask: {best_ask}')
                                print(f'Spread: {spread:.2f}%')
                            else:
                                print(f'Best Bid: {best_bid} (cannot calculate spread)')
                        else:
                            print('No bids or asks available')
                    print()

asyncio.run(test_both_tokens())
