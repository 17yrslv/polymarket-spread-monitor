import asyncio
import aiohttp
import json
from bot import PolymarketAPI

async def test_new_spread_calculation():
    """Тестирование новой логики расчета спреда"""
    
    # Создаем HTTP сессию
    async with aiohttp.ClientSession() as session:
        api = PolymarketAPI(session)
        
        print('=' * 70)
        print('TESTING NEW SPREAD CALCULATION LOGIC')
        print('=' * 70)
        
        # Получаем несколько маркетов
        markets = await api.get_all_markets(use_cache=False)
        
        if not markets:
            print('ERROR: No markets loaded')
            return
        
        print(f'\nTesting with {min(5, len(markets))} markets:\n')
        
        for i, market in enumerate(markets[:5]):
            print(f'\n--- Market {i+1} ---')
            print(f'Question: {market.get("question")}')
            
            best_bid = market.get('bestBid')
            best_ask = market.get('bestAsk')
            
            print(f'bestBid: {best_bid}')
            print(f'bestAsk: {best_ask}')
            
            # Вычисляем спред новым методом
            spread, outcome = api.calculate_spread(market)
            
            print(f'\nResult:')
            print(f'  Max Spread: {spread}%')
            print(f'  Outcome: {outcome}')
            
            # Показываем детали расчета
            if best_bid and best_ask and best_bid > 0:
                spread_yes = ((best_ask / best_bid) - 1) * 100
                no_bid = 1 - best_ask
                no_ask = 1 - best_bid
                
                if no_bid > 0:
                    spread_no = ((no_ask / no_bid) - 1) * 100
                else:
                    spread_no = 0.0
                
                print(f'\nDetails:')
                print(f'  YES: bid={best_bid}, ask={best_ask}, spread={spread_yes:.2f}%')
                print(f'  NO:  bid={no_bid:.3f}, ask={no_ask:.3f}, spread={spread_no:.2f}%')
            
            print('-' * 70)
        
        print('\n' + '=' * 70)
        print('TEST COMPLETED SUCCESSFULLY')
        print('=' * 70)

if __name__ == '__main__':
    asyncio.run(test_new_spread_calculation())
