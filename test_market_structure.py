import aiohttp
import asyncio
import json

async def test_market_structure():
    async with aiohttp.ClientSession() as session:
        print('=== Testing Market Structure ===\n')
        
        async with session.get('https://gamma-api.polymarket.com/markets?limit=1') as resp:
            markets = await resp.json()
            
            if isinstance(markets, list) and markets:
                market = markets[0]
                
                print(f'Market: {market.get("question")}\n')
                print(f'Slug: {market.get("slug")}\n')
                
                print('=== CLOB TOKEN IDS ===')
                clob_ids = market.get('clobTokenIds')
                print(f'Raw: {clob_ids}')
                print(f'Type: {type(clob_ids)}\n')
                
                if isinstance(clob_ids, str):
                    clob_ids_parsed = json.loads(clob_ids)
                    print(f'Parsed: {clob_ids_parsed}')
                    print(f'Type after parse: {type(clob_ids_parsed)}\n')
                
                print('=== OUTCOMES ===')
                outcomes = market.get('outcomes')
                print(f'Raw: {outcomes}')
                print(f'Type: {type(outcomes)}\n')
                
                if isinstance(outcomes, str):
                    outcomes_parsed = json.loads(outcomes)
                    print(f'Parsed: {outcomes_parsed}')
                    print(f'Type after parse: {type(outcomes_parsed)}\n')
                
                print('=== MARKET BID/ASK ===')
                print(f'bestBid: {market.get("bestBid")}')
                print(f'bestAsk: {market.get("bestAsk")}\n')
                
                if clob_ids:
                    if isinstance(clob_ids, str):
                        clob_ids = json.loads(clob_ids)
                    
                    if clob_ids and len(clob_ids) > 0:
                        token_id = clob_ids[0]
                        print(f'=== ORDER BOOK FOR TOKEN {token_id} ===')
                        try:
                            async with session.get(f'https://clob.polymarket.com/book?token_id={token_id}') as book_resp:
                                if book_resp.status == 200:
                                    book = await book_resp.json()
                                    bids = book.get('bids', [])
                                    asks = book.get('asks', [])
                                    print(f'Bids (first 2): {bids[:2]}')
                                    print(f'Asks (first 2): {asks[:2]}')
                                else:
                                    print(f'Status: {book_resp.status}')
                        except Exception as e:
                            print(f'Error: {e}')

asyncio.run(test_market_structure())
