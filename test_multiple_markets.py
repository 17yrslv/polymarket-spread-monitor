import aiohttp
import asyncio
import json

async def test_multiple_markets():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://gamma-api.polymarket.com/markets?limit=5') as resp:
            markets = await resp.json()
            
            for market in markets[:3]:
                print('=' * 70)
                print(f'Market: {market.get("question")}')
                print(f'Market bestBid: {market.get("bestBid")}')
                print(f'Market bestAsk: {market.get("bestAsk")}')
                
                clob_ids_str = market.get('clobTokenIds')
                outcomes_str = market.get('outcomes')
                
                if not clob_ids_str or not outcomes_str:
                    print('Missing clobTokenIds or outcomes\n')
                    continue
                
                clob_ids = json.loads(clob_ids_str)
                outcomes = json.loads(outcomes_str)
                
                print()
                for i, (token_id, outcome) in enumerate(zip(clob_ids, outcomes)):
                    print(f'  {outcome}:')
                    try:
                        async with session.get(f'https://clob.polymarket.com/book?token_id={token_id}', timeout=aiohttp.ClientTimeout(total=10)) as book_resp:
                            if book_resp.status == 200:
                                book = await book_resp.json()
                                bids = book.get('bids', [])
                                asks = book.get('asks', [])
                                
                                if bids and asks:
                                    best_bid = float(bids[0]['price'])
                                    best_ask = float(asks[0]['price'])
                                    
                                    print(f'    Bid: {best_bid}, Ask: {best_ask}')
                                    
                                    if best_bid > 0:
                                        spread = ((best_ask / best_bid) - 1) * 100
                                        print(f'    Spread: {spread:.2f}%')
                                else:
                                    print('    No bids/asks')
                            else:
                                print(f'    Status: {book_resp.status}')
                    except Exception as e:
                        print(f'    Error: {e}')
                print()

asyncio.run(test_multiple_markets())
