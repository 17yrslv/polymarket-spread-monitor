#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket Spread Monitor Bot
Асинхронный Telegram бот для мониторинга спредов на Polymarket
"""

import os
import sys
import asyncio
import aiosqlite
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from loguru import logger
import aiohttp
from aiohttp_socks import ProxyConnector
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
PROXY_URL = os.getenv("PROXY_URL", "")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
MAX_MARKETS = 5
MONITORING_INTERVAL = 10  # секунд

# Настройки автосканирования
AUTO_SCAN_INTERVAL = 60  # секунд (по умолчанию)
AUTO_SCAN_DEDUP_HOURS = 1  # часов (по умолчанию)
AUTO_SCAN_MAX_MARKETS = 1000  # максимум рынков для сканирования
AUTO_SCAN_BATCH_SIZE = 50  # обрабатывать по N рынков параллельно

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "bot.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    encoding="utf-8"
)

# ============================================================================
# POLYMARKET API CLIENT
# ============================================================================

class PolymarketAPI:
    """Клиент для работы с Polymarket API"""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self._markets_cache = None
        self._cache_time = None
        self._cache_ttl = 300  # 5 минут
    
    async def fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """Выполнить HTTP запрос с retry логикой"""
        for attempt in range(max_retries):
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.warning(f"API returned status {resp.status} for {url}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries} for {url}")
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def get_all_markets(self, use_cache: bool = True) -> Optional[List[Dict]]:
        """Получить список всех рынков с кэшированием"""
        import time
        
        # Проверка кэша
        if use_cache and self._markets_cache and self._cache_time:
            if time.time() - self._cache_time < self._cache_ttl:
                logger.info(f"Using cached markets ({len(self._markets_cache)} markets)")
                return self._markets_cache
        
        # Загрузка с API (запрашиваем больше рынков)
        logger.info("Fetching markets from API...")
        url = f"{self.BASE_URL}/markets?limit=1000&offset=0"
        data = await self.fetch_with_retry(url)
        
        if isinstance(data, list):
            self._markets_cache = data
            self._cache_time = time.time()
            logger.info(f"Loaded {len(data)} markets from API")
            return data
        
        return None
    
    async def get_market_by_slug(self, slug: str) -> Optional[Dict]:
        """Найти рынок по slug с улучшенным поиском"""
        logger.info(f"Searching for market with slug: {slug}")
        
        # Попытка 1: Прямой запрос к API (если поддерживается)
        try:
            url = f"{self.BASE_URL}/markets/{slug}"
            data = await self.fetch_with_retry(url)
            if data and isinstance(data, dict):
                logger.info(f"Found market via direct API: {data.get('question')}")
                return data
        except Exception as e:
            logger.debug(f"Direct API request failed: {e}")
        
        # Попытка 2: Поиск в списке всех рынков
        markets = await self.get_all_markets()
        if not markets:
            logger.error("Failed to load markets from API")
            return None
        
        logger.info(f"Searching through {len(markets)} markets...")
        
        # Точное совпадение slug
        for market in markets:
            if market.get("slug") == slug:
                logger.info(f"Found exact match: {market.get('question')}")
                return market
        
        # Частичное совпадение slug (если точное не найдено)
        slug_lower = slug.lower()
        for market in markets:
            market_slug = market.get("slug", "").lower()
            if slug_lower in market_slug or market_slug in slug_lower:
                logger.info(f"Found partial match: {market.get('question')} (slug: {market.get('slug')})")
                return market
        
        logger.warning(f"Market with slug '{slug}' not found")
        return None
    
    async def search_markets(self, query: str, limit: int = 10) -> List[Dict]:
        """Поиск рынков по ключевым словам"""
        markets = await self.get_all_markets()
        if not markets:
            return []
        
        query_lower = query.lower()
        results = []
        
        for market in markets:
            question = market.get("question", "").lower()
            slug = market.get("slug", "").lower()
            
            if query_lower in question or query_lower in slug:
                results.append(market)
                if len(results) >= limit:
                    break
        
        return results
    
    async def get_market_data(self, market_slug: str) -> Optional[Dict]:
        """Получить актуальные данные рынка"""
        return await self.get_market_by_slug(market_slug)
    
    @staticmethod
    def calculate_spread(market_data: Dict) -> Tuple[float, str]:
        """Рассчитать bid-ask спред для исхода YES
        
        Формула: ((bestAsk - bestBid) / bestBid) * 100
        
        Логика:
        - bestBid - лучшая цена покупки YES
        - bestAsk - лучшая цена продажи YES
        - Минимальная цена: 0.03 (3 цента)
        - Пример: bestBid=0.54, bestAsk=0.55: ((0.55-0.54)/0.54)*100 = 1.85%
        
        Returns:
            Tuple[float, str]: (spread, "Yes")
        """
        try:
            best_bid = float(market_data.get("bestBid", 0))
            best_ask = float(market_data.get("bestAsk", 0))
            
            # Проверка на нулевые значения
            if best_bid == 0 or best_ask == 0:
                return 0.0, "Unknown"
            
            # Проверка минимальной цены (3 цента)
            if best_bid < 0.03 or best_ask < 0.03:
                return 0.0, "Unknown"
            
            # Формула: ((bestAsk - bestBid) / bestBid) * 100
            spread = ((best_ask - best_bid) / best_bid) * 100
            
            return round(spread, 2), "Yes"
                
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.error(f"Error calculating spread: {e}")
            return 0.0, "Unknown"
    
    async def get_markets_by_categories(self, categories: List[str], limit: int = AUTO_SCAN_MAX_MARKETS) -> List[Dict]:
        """Получить рынки по категориям (groupItemTitle)"""
        try:
            markets = await self.get_all_markets(use_cache=True)
            if not markets:
                logger.warning("No markets loaded from API")
                return []
            
            # Фильтруем по категориям
            filtered_markets = []
            categories_lower = [cat.lower() for cat in categories]
            
            for market in markets:
                group_title = market.get("groupItemTitle", "")
                if group_title and group_title.lower() in categories_lower:
                    filtered_markets.append(market)
                    if len(filtered_markets) >= limit:
                        break
            
            logger.info(f"Filtered {len(filtered_markets)} markets from {len(categories)} categories")
            return filtered_markets
        
        except Exception as e:
            logger.error(f"Error filtering markets by categories: {e}")
            return []
    
    async def get_all_active_markets(self, min_volume: float = 0, limit: int = AUTO_SCAN_MAX_MARKETS) -> List[Dict]:
        """Получить все активные рынки с минимальным объемом"""
        try:
            markets = await self.get_all_markets(use_cache=True)
            if not markets:
                logger.warning("No markets loaded from API")
                return []
            
            # Фильтруем активные рынки
            active_markets = []
            for market in markets:
                # Проверяем что рынок активен
                if market.get("closed") or market.get("archived"):
                    continue
                
                # Проверяем минимальный объем
                volume = float(market.get("volume", 0))
                if volume < min_volume:
                    continue
                
                active_markets.append(market)
                if len(active_markets) >= limit:
                    break
            
            logger.info(f"Found {len(active_markets)} active markets (min volume: ${min_volume:,.0f})")
            return active_markets
        
        except Exception as e:
            logger.error(f"Error getting active markets: {e}")
            return []
    
    async def get_all_unique_categories(self) -> List[str]:
        """Получить список всех уникальных категорий (groupItemTitle)"""
        try:
            markets = await self.get_all_markets(use_cache=True)
            if not markets:
                return []
            
            categories = set()
            for market in markets:
                group_title = market.get("groupItemTitle")
                if group_title and group_title.strip():
                    categories.add(group_title.strip())
            
            sorted_categories = sorted(categories)
            logger.info(f"Found {len(sorted_categories)} unique categories")
            return sorted_categories
        
        except Exception as e:
            logger.error(f"Error getting unique categories: {e}")
            return []

# ============================================================================
# DATABASE
# ============================================================================

class Database:
    """Управление SQLite базой данных"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS markets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    market_slug TEXT NOT NULL,
                    market_name TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, market_slug)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS filters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    filter_type TEXT NOT NULL,
                    filter_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, filter_type)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_state (
                    user_id INTEGER PRIMARY KEY,
                    is_active INTEGER DEFAULT 1,
                    last_update TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Настройки автоматического сканирования
            await db.execute("""
                CREATE TABLE IF NOT EXISTS auto_scan_settings (
                    user_id INTEGER PRIMARY KEY,
                    is_enabled INTEGER DEFAULT 0,
                    scan_mode TEXT DEFAULT 'all',
                    scan_interval INTEGER DEFAULT 60,
                    dedup_hours INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Выбранные категории для сканирования
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scan_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, category)
                )
            """)
            
            # История отправленных уведомлений (для дедупликации)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    market_slug TEXT NOT NULL,
                    spread_value REAL NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Индекс для быстрого поиска
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_history 
                ON notification_history(user_id, market_slug, sent_at)
            """)
            
            await db.commit()
        
        logger.info("Database initialized")
    
    async def add_user(self, user_id: int):
        """Добавить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (user_id,)
            )
            await db.commit()
    
    async def add_market(self, user_id: int, market_slug: str, market_name: str) -> bool:
        """Добавить рынок для мониторинга"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO markets (user_id, market_slug, market_name) VALUES (?, ?, ?)",
                    (user_id, market_slug, market_name)
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False
    
    async def remove_market(self, user_id: int, market_slug: str) -> bool:
        """Удалить рынок"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM markets WHERE user_id = ? AND market_slug = ?",
                (user_id, market_slug)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def get_user_markets(self, user_id: int) -> List[Dict]:
        """Получить все рынки пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT market_slug, market_name FROM markets WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_markets_count(self, user_id: int) -> int:
        """Получить количество рынков пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM markets WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def set_filter(self, user_id: int, filter_type: str, filter_value: str):
        """Установить фильтр"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO filters (user_id, filter_type, filter_value) VALUES (?, ?, ?)",
                (user_id, filter_type, filter_value)
            )
            await db.commit()
    
    async def get_filters(self, user_id: int) -> List[Dict]:
        """Получить все фильтры пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT filter_type, filter_value FROM filters WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def clear_filter(self, user_id: int, filter_type: str) -> bool:
        """Удалить фильтр"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM filters WHERE user_id = ? AND filter_type = ?",
                (user_id, filter_type)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def set_monitoring_state(self, user_id: int, is_active: bool):
        """Установить состояние мониторинга"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO monitoring_state (user_id, is_active, last_update) VALUES (?, ?, ?)",
                (user_id, 1 if is_active else 0, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()
    
    async def get_monitoring_state(self, user_id: int) -> bool:
        """Получить состояние мониторинга"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT is_active FROM monitoring_state WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False
    
    # ========================================================================
    # AUTO SCAN SETTINGS
    # ========================================================================
    
    async def set_auto_scan_settings(self, user_id: int, **kwargs):
        """Установить настройки автосканирования"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получить текущие настройки
            cursor = await db.execute(
                "SELECT is_enabled, scan_mode, scan_interval, dedup_hours FROM auto_scan_settings WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                # Обновить существующие настройки
                is_enabled = kwargs.get('is_enabled', row[0])
                scan_mode = kwargs.get('scan_mode', row[1])
                scan_interval = kwargs.get('scan_interval', row[2])
                dedup_hours = kwargs.get('dedup_hours', row[3])
            else:
                # Создать новые настройки с дефолтными значениями
                is_enabled = kwargs.get('is_enabled', 0)
                scan_mode = kwargs.get('scan_mode', 'all')
                scan_interval = kwargs.get('scan_interval', 60)
                dedup_hours = kwargs.get('dedup_hours', 1)
            
            await db.execute(
                """INSERT OR REPLACE INTO auto_scan_settings 
                   (user_id, is_enabled, scan_mode, scan_interval, dedup_hours) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, is_enabled, scan_mode, scan_interval, dedup_hours)
            )
            await db.commit()
    
    async def get_auto_scan_settings(self, user_id: int) -> Dict:
        """Получить настройки автосканирования"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT is_enabled, scan_mode, scan_interval, dedup_hours FROM auto_scan_settings WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    'is_enabled': bool(row[0]),
                    'scan_mode': row[1],
                    'scan_interval': row[2],
                    'dedup_hours': row[3]
                }
            else:
                # Вернуть дефолтные настройки
                return {
                    'is_enabled': False,
                    'scan_mode': 'all',
                    'scan_interval': 60,
                    'dedup_hours': 1
                }
    
    # ========================================================================
    # SCAN CATEGORIES
    # ========================================================================
    
    async def add_scan_category(self, user_id: int, category: str) -> bool:
        """Добавить категорию для сканирования"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO scan_categories (user_id, category) VALUES (?, ?)",
                    (user_id, category)
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False
            except Exception as e:
                logger.error(f"Error adding scan category: {e}")
                return False
    
    async def remove_scan_category(self, user_id: int, category: str) -> bool:
        """Удалить категорию"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute(
                    "DELETE FROM scan_categories WHERE user_id = ? AND category = ?",
                    (user_id, category)
                )
                await db.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"Error removing scan category: {e}")
                return False
    
    async def get_scan_categories(self, user_id: int) -> List[str]:
        """Получить все категории пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute(
                    "SELECT category FROM scan_categories WHERE user_id = ?",
                    (user_id,)
                )
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
            except Exception as e:
                logger.error(f"Error getting scan categories: {e}")
                return []
    
    async def clear_scan_categories(self, user_id: int):
        """Очистить все категории пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "DELETE FROM scan_categories WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Error clearing scan categories: {e}")
    
    # ========================================================================
    # NOTIFICATION HISTORY
    # ========================================================================
    
    async def save_notification(self, user_id: int, market_slug: str, spread: float):
        """Сохранить отправленное уведомление"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO notification_history (user_id, market_slug, spread_value) VALUES (?, ?, ?)",
                    (user_id, market_slug, spread)
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Error saving notification: {e}")
    
    async def get_last_notification(self, user_id: int, market_slug: str) -> Optional[datetime]:
        """Получить время последнего уведомления для рынка"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute(
                    """SELECT sent_at FROM notification_history 
                       WHERE user_id = ? AND market_slug = ? 
                       ORDER BY sent_at DESC LIMIT 1""",
                    (user_id, market_slug)
                )
                row = await cursor.fetchone()
                if row:
                    return datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
                return None
            except Exception as e:
                logger.error(f"Error getting last notification: {e}")
                return None
    
    async def cleanup_old_notifications(self, days: int = 7):
        """Очистить старые уведомления"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
                await db.execute(
                    "DELETE FROM notification_history WHERE sent_at < ?",
                    (cutoff_date.isoformat(),)
                )
                await db.commit()
                logger.info(f"Cleaned up notifications older than {days} days")
            except Exception as e:
                logger.error(f"Error cleaning up notifications: {e}")

# ============================================================================
# MONITORING SERVICE
# ============================================================================

class MonitoringService:
    """Сервис фонового мониторинга рынков"""
    
    def __init__(self, bot: Bot, db: Database, api: PolymarketAPI):
        self.bot = bot
        self.db = db
        self.api = api
        self.tasks: Dict[int, asyncio.Task] = {}
    
    async def start_monitoring(self, user_id: int):
        """Запустить мониторинг для пользователя"""
        if user_id in self.tasks and not self.tasks[user_id].done():
            logger.info(f"Monitoring already running for user {user_id}")
            return
        
        await self.db.set_monitoring_state(user_id, True)
        self.tasks[user_id] = asyncio.create_task(self._monitoring_loop(user_id))
        logger.info(f"Started monitoring for user {user_id}")
    
    async def stop_monitoring(self, user_id: int):
        """Остановить мониторинг для пользователя"""
        if user_id in self.tasks:
            self.tasks[user_id].cancel()
            try:
                await self.tasks[user_id]
            except asyncio.CancelledError:
                pass
            del self.tasks[user_id]
        
        await self.db.set_monitoring_state(user_id, False)
        logger.info(f"Stopped monitoring for user {user_id}")
    
    async def _monitoring_loop(self, user_id: int):
        """Основной цикл мониторинга"""
        while True:
            try:
                markets = await self.db.get_user_markets(user_id)
                filters = await self.db.get_filters(user_id)
                
                for market in markets:
                    try:
                        data = await self.api.get_market_data(market["market_slug"])
                        if not data:
                            logger.warning(f"No data for market {market['market_slug']}")
                            continue
                        
                        spread, outcome = self.api.calculate_spread(data)
                        
                        if self._check_filters(data, spread, filters):
                            await self._send_notification(user_id, data, spread, outcome)
                    
                    except Exception as e:
                        logger.error(f"Error processing market {market['market_slug']}: {e}")
                
                await asyncio.sleep(MONITORING_INTERVAL)
            
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for user {user_id}")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(MONITORING_INTERVAL)
    
    def _check_filters(self, data: Dict, spread: float, filters: List[Dict]) -> bool:
        """Проверить соответствие данных фильтрам"""
        if not filters:
            return True
        
        for filter_item in filters:
            filter_type = filter_item["filter_type"]
            filter_value = filter_item["filter_value"]
            
            try:
                if filter_type == "spread_min":
                    min_spread = float(filter_value)
                    if spread < min_spread:
                        return False
                
                elif filter_type == "volume_min":
                    min_volume = float(filter_value)
                    volume = float(data.get("volume", 0))
                    if volume < min_volume:
                        return False
                
                elif filter_type == "yes_price_between":
                    min_price, max_price = map(float, filter_value.split(","))
                    outcome_prices = data.get("outcomePrices", "[]")
                    if isinstance(outcome_prices, str):
                        import json
                        outcome_prices = json.loads(outcome_prices)
                    
                    if outcome_prices and len(outcome_prices) > 0:
                        yes_price = float(outcome_prices[0])
                        if not (min_price <= yes_price <= max_price):
                            return False
            
            except (ValueError, TypeError, IndexError) as e:
                logger.error(f"Error checking filter {filter_type}: {e}")
                continue
        
        return True
    
    async def _send_notification(self, user_id: int, data: Dict, spread: float, outcome: str):
        """Отправить уведомление пользователю"""
        try:
            question = data.get("question", "Unknown Market")
            slug = data.get("slug", "")
            best_bid = float(data.get("bestBid", 0))
            best_ask = float(data.get("bestAsk", 0))
            volume = float(data.get("volume", 0))
            liquidity = float(data.get("liquidity", 0))
            
            outcome_prices = data.get("outcomePrices", "[]")
            if isinstance(outcome_prices, str):
                import json
                outcome_prices = json.loads(outcome_prices)
            
            yes_price = float(outcome_prices[0]) if outcome_prices and len(outcome_prices) > 0 else 0
            no_price = float(outcome_prices[1]) if outcome_prices and len(outcome_prices) > 1 else 0
            
            current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
            
            # Формируем ссылку на маркет
            events = data.get("events", [])
            if isinstance(events, str):
                import json
                events = json.loads(events)
            
            if events and len(events) > 0 and slug:
                event_slug = events[0].get("slug", "")
                market_url = f"https://polymarket.com/event/{event_slug}/{slug}"
            elif slug:
                market_url = f"https://polymarket.com/event/{slug}"
            else:
                market_url = ""
            
            message = (
                f"🏛️ Рынок: {question}\n"
                f"📊 Спред: {spread}% ({outcome})\n"
                f"Yes: {yes_price:.3f} | No: {no_price:.3f}\n"
                f"Объём: ${volume:,.0f}\n"
                f"Ликвидность: ${liquidity:,.0f}\n"
            )
            
            if market_url:
                message += f"🔗 Ссылка: {market_url}\n"
            
            message += f"Последнее обновление: {current_time}"
            
            await self.bot.send_message(user_id, message)
        
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

# ============================================================================
# AUTO SCAN SERVICE
# ============================================================================

class AutoScanService:
    """Сервис автоматического сканирования рынков"""
    
    def __init__(self, bot: Bot, db: Database, api: PolymarketAPI):
        self.bot = bot
        self.db = db
        self.api = api
        self.scan_tasks: Dict[int, asyncio.Task] = {}
    
    async def start_auto_scan(self, user_id: int):
        """Запустить автоматическое сканирование"""
        if user_id in self.scan_tasks and not self.scan_tasks[user_id].done():
            logger.info(f"Auto scan already running for user {user_id}")
            return
        
        await self.db.set_auto_scan_settings(user_id, is_enabled=1)
        self.scan_tasks[user_id] = asyncio.create_task(self._scan_loop(user_id))
        logger.info(f"Started auto scan for user {user_id}")
    
    async def stop_auto_scan(self, user_id: int):
        """Остановить автоматическое сканирование"""
        if user_id in self.scan_tasks:
            self.scan_tasks[user_id].cancel()
            try:
                await self.scan_tasks[user_id]
            except asyncio.CancelledError:
                pass
            del self.scan_tasks[user_id]
        
        await self.db.set_auto_scan_settings(user_id, is_enabled=0)
        logger.info(f"Stopped auto scan for user {user_id}")
    
    async def _scan_loop(self, user_id: int):
        """Основной цикл сканирования"""
        while True:
            try:
                # Получить настройки пользователя
                settings = await self.db.get_auto_scan_settings(user_id)
                scan_mode = settings.get('scan_mode', 'all')
                scan_interval = settings.get('scan_interval', AUTO_SCAN_INTERVAL)
                dedup_hours = settings.get('dedup_hours', AUTO_SCAN_DEDUP_HOURS)
                
                # Получить фильтры
                filters = await self.db.get_filters(user_id)
                
                # Загрузить рынки в зависимости от режима
                if scan_mode == 'categories':
                    categories = await self.db.get_scan_categories(user_id)
                    if not categories:
                        logger.warning(f"User {user_id} has no categories selected, skipping scan")
                        await asyncio.sleep(scan_interval)
                        continue
                    
                    markets = await self.api.get_markets_by_categories(categories)
                else:  # scan_mode == 'all'
                    markets = await self.api.get_all_active_markets(min_volume=0)
                
                if not markets:
                    logger.warning(f"No markets to scan for user {user_id}")
                    await asyncio.sleep(scan_interval)
                    continue
                
                logger.info(f"Scanning {len(markets)} markets for user {user_id}")
                
                # Счетчики для статистики
                passed_filters = 0
                blocked_by_dedup = 0
                sent_notifications = 0
                
                # Обрабатываем рынки батчами для оптимизации
                for i in range(0, len(markets), AUTO_SCAN_BATCH_SIZE):
                    batch = markets[i:i + AUTO_SCAN_BATCH_SIZE]
                    stats = await self._process_batch(user_id, batch, filters, dedup_hours)
                    passed_filters += stats.get('passed_filters', 0)
                    blocked_by_dedup += stats.get('blocked_by_dedup', 0)
                    sent_notifications += stats.get('sent_notifications', 0)
                    
                    # Небольшая задержка между батчами чтобы не перегружать API
                    if i + AUTO_SCAN_BATCH_SIZE < len(markets):
                        await asyncio.sleep(1)
                
                # Очистка старых уведомлений
                await self.db.cleanup_old_notifications(days=7)
                
                logger.info(f"Scan completed for user {user_id}: {len(markets)} markets scanned, {passed_filters} passed filters, {blocked_by_dedup} blocked by dedup, {sent_notifications} notifications sent, sleeping for {scan_interval}s")
                await asyncio.sleep(scan_interval)
            
            except asyncio.CancelledError:
                logger.info(f"Auto scan cancelled for user {user_id}")
                break
            except Exception as e:
                logger.error(f"Error in auto scan loop for user {user_id}: {e}")
                await asyncio.sleep(scan_interval)
    
    async def _process_batch(self, user_id: int, markets: List[Dict], filters: List[Dict], dedup_hours: int):
        """Обработать батч рынков"""
        tasks = []
        for market in markets:
            task = self._process_market(user_id, market, filters, dedup_hours)
            tasks.append(task)
        
        # Обрабатываем все рынки в батче параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Подсчитываем статистику
        stats = {
            'passed_filters': 0,
            'blocked_by_dedup': 0,
            'sent_notifications': 0
        }
        
        for result in results:
            if isinstance(result, dict):
                stats['passed_filters'] += result.get('passed_filters', 0)
                stats['blocked_by_dedup'] += result.get('blocked_by_dedup', 0)
                stats['sent_notifications'] += result.get('sent_notifications', 0)
        
        return stats
    
    async def _process_market(self, user_id: int, market: Dict, filters: List[Dict], dedup_hours: int):
        """Обработать один рынок"""
        try:
            market_slug = market.get('slug')
            if not market_slug:
                return {}
            
            # Рассчитываем спред
            spread, outcome = self.api.calculate_spread(market)
            
            # Проверяем фильтры
            if not self._check_filters(market, spread, filters):
                return {}
            
            # Рынок прошел фильтры
            passed_filters = 1
            
            # Проверяем дедупликацию
            if not await self._should_notify(user_id, market_slug, dedup_hours):
                return {'passed_filters': passed_filters, 'blocked_by_dedup': 1, 'sent_notifications': 0}
            
            # Отправляем уведомление
            await self._send_notification(user_id, market, spread, outcome)
            
            # Сохраняем в историю
            await self.db.save_notification(user_id, market_slug, spread)
            
            return {'passed_filters': passed_filters, 'blocked_by_dedup': 0, 'sent_notifications': 1}
        
        except Exception as e:
            logger.error(f"Error processing market {market.get('slug', 'unknown')}: {e}")
            return {}
    
    def _check_filters(self, market: Dict, spread: float, filters: List[Dict]) -> bool:
        """Проверить соответствие рынка фильтрам"""
        if not filters:
            return True
        
        try:
            for filter_item in filters:
                filter_type = filter_item["filter_type"]
                filter_value = filter_item["filter_value"]
                
                if filter_type == "spread_min":
                    min_spread = float(filter_value)
                    if spread < min_spread:
                        return False
                
                elif filter_type == "volume_min":
                    min_volume = float(filter_value)
                    volume = float(market.get("volume", 0))
                    if volume < min_volume:
                        return False
                
                elif filter_type == "yes_price_between":
                    min_price, max_price = map(float, filter_value.split(","))
                    outcome_prices = market.get("outcomePrices", "[]")
                    if isinstance(outcome_prices, str):
                        import json
                        outcome_prices = json.loads(outcome_prices)
                    
                    if outcome_prices and len(outcome_prices) > 0:
                        yes_price = float(outcome_prices[0])
                        if not (min_price <= yes_price <= max_price):
                            return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error checking filters: {e}")
            return False
    
    async def _should_notify(self, user_id: int, market_slug: str, dedup_hours: int) -> bool:
        """Проверить, нужно ли отправлять уведомление (дедупликация)"""
        try:
            last_notification = await self.db.get_last_notification(user_id, market_slug)
            
            if last_notification is None:
                logger.debug(f"Market {market_slug}: never notified before, will notify")
                return True
            
            # Проверяем прошло ли достаточно времени
            time_diff = datetime.now(timezone.utc) - last_notification
            hours_passed = time_diff.total_seconds() / 3600
            
            should_notify = hours_passed >= dedup_hours
            logger.debug(f"Market {market_slug}: last notified {hours_passed:.2f}h ago, dedup={dedup_hours}h, will_notify={should_notify}")
            
            return should_notify
        
        except Exception as e:
            logger.error(f"Error checking notification deduplication: {e}")
            return True  # В случае ошибки разрешаем отправку
    
    async def _send_notification(self, user_id: int, market: Dict, spread: float, outcome: str):
        """Отправить уведомление пользователю"""
        try:
            question = market.get("question", "Unknown Market")
            best_bid = float(market.get("bestBid", 0))
            best_ask = float(market.get("bestAsk", 0))
            volume = float(market.get("volume", 0))
            liquidity = float(market.get("liquidity", 0))
            slug = market.get("slug", "")
            
            outcome_prices = market.get("outcomePrices", "[]")
            if isinstance(outcome_prices, str):
                import json
                outcome_prices = json.loads(outcome_prices)
            
            yes_price = float(outcome_prices[0]) if outcome_prices and len(outcome_prices) > 0 else 0
            no_price = float(outcome_prices[1]) if outcome_prices and len(outcome_prices) > 1 else 0
            
            current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
            
            # Формируем ссылку на маркет
            events = market.get("events", [])
            if isinstance(events, str):
                import json
                events = json.loads(events)
            
            if events and len(events) > 0 and slug:
                event_slug = events[0].get("slug", "")
                market_url = f"https://polymarket.com/event/{event_slug}/{slug}"
            elif slug:
                market_url = f"https://polymarket.com/event/{slug}"
            else:
                market_url = ""
            
            message = (
                f"🔔 Найден рынок!\n\n"
                f"🏛️ {question}\n\n"
                f"📊 Спред: {spread}% ({outcome})\n"
                f"💰 Yes: {yes_price:.3f} | No: {no_price:.3f}\n"
                f"📈 Объём: ${volume:,.0f}\n"
                f"💧 Ликвидность: ${liquidity:,.0f}\n"
            )
            
            if market_url:
                message += f"🔗 Ссылка: {market_url}\n"
            
            message += f"\n⏰ {current_time}"
            
            await self.bot.send_message(user_id, message)
            logger.info(f"Sent notification to user {user_id} for market {slug}")
        
        except Exception as e:
            logger.error(f"Error sending auto scan notification: {e}")

# ============================================================================
# KEYBOARD HELPERS
# ============================================================================

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Создать главное меню с кнопками"""
    keyboard = [
        [
            KeyboardButton(text="🔍 Поиск"),
            KeyboardButton(text="📊 Мои рынки"),
            KeyboardButton(text="🎯 Фильтры")
        ],
        [
            KeyboardButton(text="🤖 Автоскан"),
            KeyboardButton(text="📈 Статус"),
            KeyboardButton(text="❓ Помощь")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ============================================================================
# BOT HANDLERS
# ============================================================================

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, db: Database):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    await db.add_user(user_id)
    
    markets_count = await db.get_markets_count(user_id)
    is_active = await db.get_monitoring_state(user_id)
    filters = await db.get_filters(user_id)
    auto_scan_settings = await db.get_auto_scan_settings(user_id)
    
    status = "активен ✅" if is_active else "остановлен ⏸️"
    filters_text = f"{len(filters)} активных" if filters else "не установлены"
    auto_scan_status = "активно ✅" if auto_scan_settings['is_enabled'] else "остановлено ⏸️"
    
    text = (
        "👋 Добро пожаловать в Polymarket Spread Monitor!\n\n"
        "📊 Мониторинг конкретных рынков:\n"
        f"• Рынков: {markets_count}/{MAX_MARKETS}\n"
        f"• Статус: {status}\n\n"
        "🔍 Автосканирование:\n"
        f"• Статус: {auto_scan_status}\n"
        f"• Режим: {auto_scan_settings['scan_mode']}\n"
        f"• Фильтры: {filters_text}\n\n"
        "📝 Основные команды:\n"
        "/search <запрос> - найти рынки\n"
        "/set_market <slug> - добавить рынок\n"
        "/markets - список рынков\n"
        "/set_filter <type> <value> - установить фильтр\n"
        "/filters - показать фильтры\n\n"
        "🤖 Автосканирование:\n"
        "/auto_scan_start - запустить\n"
        "/auto_scan_stop - остановить\n"
        "/auto_scan_status - статус\n"
        "/auto_scan_mode <all|categories> - режим\n"
        "/categories - список категорий\n"
        "/add_category <название> - добавить категорию\n"
        "/my_categories - мои категории"
    )
    
    await message.answer(text, reply_markup=get_main_menu_keyboard())

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    text = (
        "📚 Справка по командам Polymarket Spread Monitor\n\n"
        
        "🔍 ПОИСК И УПРАВЛЕНИЕ РЫНКАМИ\n"
        "/search <запрос> - найти рынки по ключевым словам\n"
        "/set_market <slug> - добавить рынок в мониторинг\n"
        "/markets - показать список отслеживаемых рынков\n"
        "/remove_market <slug> - удалить рынок из мониторинга\n\n"
        
        "🎯 ФИЛЬТРЫ\n"
        "/set_filter <type> <value> - установить фильтр\n"
        "  Типы: min_spread, max_spread, min_volume, max_volume, min_liquidity\n"
        "  Пример: /set_filter min_spread 5\n"
        "/filters - показать активные фильтры\n"
        "/remove_filter <id> - удалить фильтр по ID\n\n"
        
        "📊 МОНИТОРИНГ КОНКРЕТНЫХ РЫНКОВ\n"
        "/status - показать статус мониторинга\n"
        "/stop - остановить мониторинг\n\n"
        
        "🤖 АВТОСКАНИРОВАНИЕ\n"
        "/auto_scan_start - запустить автосканирование\n"
        "/auto_scan_stop - остановить автосканирование\n"
        "/auto_scan_status - показать статус автосканирования\n"
        "/auto_scan_mode <all|categories> - установить режим сканирования\n"
        "/auto_scan_interval <секунды> - установить интервал сканирования\n"
        "/auto_scan_dedup <часы> - установить время дедупликации\n\n"
        
        "📁 КАТЕГОРИИ (для режима categories)\n"
        "/categories - показать доступные категории\n"
        "/add_category <название> - добавить категорию для сканирования\n"
        "/remove_category <название> - удалить категорию\n"
        "/my_categories - показать мои категории\n\n"
        
        "💡 ПОДСКАЗКИ\n"
        "• Максимум рынков в мониторинге: 5\n"
        "• Интервал проверки: 10 секунд\n"
        "• Используйте фильтры для точной настройки уведомлений\n"
        "• Автосканирование работает независимо от мониторинга конкретных рынков"
    )
    
    await message.answer(text, reply_markup=get_main_menu_keyboard())

@router.message(Command("set_market"))
async def cmd_set_market(message: Message, db: Database, api: PolymarketAPI, monitoring: MonitoringService):
    """Обработчик команды /set_market"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /set_market <slug>\n\n"
            "Пример:\n"
            "/set_market russia-ukraine-ceasefire-before-gta-vi-554\n\n"
            "💡 Не знаете slug? Используйте:\n"
            "/search <ключевые слова>"
        )
        return
    
    slug = args[1].strip()
    
    markets_count = await db.get_markets_count(user_id)
    if markets_count >= MAX_MARKETS:
        await message.answer(f"❌ Достигнут лимит рынков ({MAX_MARKETS}). Удалите существующий рынок командой /remove_market")
        return
    
    await message.answer("🔍 Поиск рынка...")
    
    market_data = await api.get_market_by_slug(slug)
    if not market_data:
        await message.answer(
            f"❌ Рынок с slug '{slug}' не найден\n\n"
            "Возможные причины:\n"
            "• Неправильный slug (проверьте написание)\n"
            "• Рынок закрыт или удалён\n"
            "• Рынок ещё не загружен в кэш\n\n"
            "💡 Попробуйте найти рынок:\n"
            f"/search {slug.split('-')[0] if '-' in slug else slug}"
        )
        return
    
    market_name = market_data.get("question", "Unknown")
    success = await db.add_market(user_id, slug, market_name)
    
    if not success:
        await message.answer("❌ Этот рынок уже добавлен")
        return
    
    await message.answer(f"✅ Рынок добавлен: {market_name}")
    
    is_active = await db.get_monitoring_state(user_id)
    if not is_active:
        await monitoring.start_monitoring(user_id)
        await message.answer("🚀 Мониторинг запущен!")

@router.message(Command("markets"))
async def cmd_markets(message: Message, db: Database):
    """Обработчик команды /markets"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    markets = await db.get_user_markets(user_id)
    
    if not markets:
        await message.answer("📋 У вас нет отслеживаемых рынков\n\nДобавьте рынок командой:\n/set_market <slug>")
        return
    
    text = f"📋 Ваши рынки ({len(markets)}/{MAX_MARKETS}):\n\n"
    buttons = []
    
    for i, market in enumerate(markets, 1):
        market_name = market['market_name']
        market_slug = market['market_slug']
        
        text += f"{i}. {market_name}\n   🔗 {market_slug}\n\n"
        
        # Добавляем кнопку удаления для каждого рынка
        buttons.append([InlineKeyboardButton(
            text=f"🗑️ Удалить рынок {i}",
            callback_data=f"remove_market:{market_slug}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)

@router.message(Command("remove_market"))
async def cmd_remove_market(message: Message, db: Database, monitoring: MonitoringService):
    """Обработчик команды /remove_market"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /remove_market <slug>")
        return
    
    slug = args[1].strip()
    success = await db.remove_market(user_id, slug)
    
    if success:
        await message.answer(f"✅ Рынок удалён: {slug}")
        
        markets_count = await db.get_markets_count(user_id)
        if markets_count == 0:
            await monitoring.stop_monitoring(user_id)
            await message.answer("⏸️ Мониторинг остановлен (нет рынков)")
    else:
        await message.answer(f"❌ Рынок '{slug}' не найден в вашем списке")

@router.message(Command("set_filter"))
async def cmd_set_filter(message: Message, db: Database):
    """Обработчик команды /set_filter"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ Использование:\n"
            "/set_filter spread_min <значение>\n"
            "/set_filter volume_min <значение>\n"
            "/set_filter yes_price_between <min> <max>\n\n"
            "Примеры:\n"
            "/set_filter spread_min 1.5\n"
            "/set_filter volume_min 500000\n"
            "/set_filter yes_price_between 0.4 0.6"
        )
        return
    
    filter_type = args[1]
    
    if filter_type == "yes_price_between":
        if len(args) < 4:
            await message.answer("❌ Для yes_price_between нужно указать min и max значения")
            return
        filter_value = f"{args[2]},{args[3]}"
    else:
        filter_value = args[2]
    
    if filter_type not in ["spread_min", "volume_min", "yes_price_between"]:
        await message.answer("❌ Неизвестный тип фильтра. Доступные: spread_min, volume_min, yes_price_between")
        return
    
    await db.set_filter(user_id, filter_type, filter_value)
    
    if filter_type == "spread_min":
        await message.answer(f"✅ Фильтр установлен: минимальный спред {filter_value}%")
    elif filter_type == "volume_min":
        await message.answer(f"✅ Фильтр установлен: минимальный объём ${filter_value}")
    elif filter_type == "yes_price_between":
        min_val, max_val = filter_value.split(",")
        await message.answer(f"✅ Фильтр установлен: цена Yes между {min_val} и {max_val}")

@router.message(Command("filters"))
async def cmd_filters(message: Message, db: Database):
    """Обработчик команды /filters"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    filters = await db.get_filters(user_id)
    
    if not filters:
        await message.answer("🔍 У вас нет активных фильтров\n\nУстановите фильтр командой:\n/set_filter <type> <value>")
        return
    
    text = "🔍 Активные фильтры:\n\n"
    buttons = []
    
    for filter_item in filters:
        filter_id = filter_item["id"]
        filter_type = filter_item["filter_type"]
        filter_value = filter_item["filter_value"]
        
        if filter_type == "spread_min":
            text += f"ID {filter_id}: Минимальный спред: {filter_value}%\n"
        elif filter_type == "volume_min":
            text += f"ID {filter_id}: Минимальный объём: ${filter_value}\n"
        elif filter_type == "yes_price_between":
            min_val, max_val = filter_value.split(",")
            text += f"ID {filter_id}: Цена Yes: между {min_val} и {max_val}\n"
        
        # Добавляем кнопку для удаления каждого фильтра
        buttons.append([InlineKeyboardButton(
            text=f"🗑️ Удалить фильтр {filter_id}",
            callback_data=f"remove_filter:{filter_id}"
        )])
    
    # Добавляем кнопку для очистки всех фильтров
    buttons.append([InlineKeyboardButton(
        text="🧹 Очистить все фильтры",
        callback_data="clear_all_filters"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)

@router.message(Command("status"))
async def cmd_status(message: Message, db: Database):
    """Обработчик команды /status"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    is_active = await db.get_monitoring_state(user_id)
    markets_count = await db.get_markets_count(user_id)
    filters_count = len(await db.get_filters(user_id))
    
    status = "активен ✅" if is_active else "остановлен ⏸️"
    
    text = (
        "📊 Статус мониторинга:\n\n"
        f"• Состояние: {status}\n"
        f"• Рынков: {markets_count}/{MAX_MARKETS}\n"
        f"• Фильтров: {filters_count}\n"
        f"• Интервал обновления: {MONITORING_INTERVAL} сек"
    )
    
    # Добавляем кнопки управления мониторингом
    buttons = []
    
    if markets_count > 0:
        if is_active:
            buttons.append([InlineKeyboardButton(
                text="⏸️ Остановить мониторинг",
                callback_data="monitoring_stop"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text="▶️ Запустить мониторинг",
                callback_data="monitoring_start"
            )])
    
    if buttons:
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text)

@router.message(Command("stop"))
async def cmd_stop(message: Message, db: Database, monitoring: MonitoringService):
    """Обработчик команды /stop"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    await monitoring.stop_monitoring(user_id)
    await message.answer("⏸️ Мониторинг остановлен")

@router.message(Command("search"))
async def cmd_search(message: Message, api: PolymarketAPI):
    """Обработчик команды /search"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /search <ключевые слова>\n\n"
            "Примеры:\n"
            "/search Trump\n"
            "/search Ukraine ceasefire\n"
            "/search GTA VI"
        )
        return
    
    query = args[1].strip()
    await message.answer(f"🔍 Поиск рынков по запросу: {query}\n\nПожалуйста, подождите...")
    
    try:
        results = await api.search_markets(query, limit=10)
        
        if not results:
            await message.answer(
                f"❌ Рынки по запросу '{query}' не найдены\n\n"
                "Попробуйте:\n"
                "• Использовать другие ключевые слова\n"
                "• Проверить правильность написания\n"
                "• Искать на английском языке"
            )
            return
        
        # Отправляем результаты с inline кнопками
        for i, market in enumerate(results[:5], 1):  # Показываем первые 5 результатов
            question = market.get("question", "Unknown")
            slug = market.get("slug", "unknown")
            volume = float(market.get("volume", 0))
            
            text = (
                f"🔍 Результат {i}/{min(len(results), 5)}\n\n"
                f"📊 {question}\n\n"
                f"🔗 Slug: {slug}\n"
                f"💰 Объём: ${volume:,.0f}"
            )
            
            # Создаём inline кнопку для добавления рынка
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить рынок", callback_data=f"add_market:{slug}")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
        
        if len(results) > 5:
            await message.answer(f"ℹ️ Показано 5 из {len(results)} найденных рынков")
    
    except Exception as e:
        logger.error(f"Error in search command: {e}")
        await message.answer(f"❌ Ошибка при поиске: {str(e)}")

# ============================================================================
# AUTO SCAN COMMANDS
# ============================================================================

@router.message(Command("auto_scan_start"))
async def cmd_auto_scan_start(message: Message, db: Database, auto_scan: AutoScanService):
    """Обработчик команды /auto_scan_start"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    settings = await db.get_auto_scan_settings(user_id)
    
    if settings['is_enabled']:
        await message.answer("ℹ️ Автосканирование уже запущено")
        return
    
    # Проверяем настройки
    if settings['scan_mode'] == 'categories':
        categories = await db.get_scan_categories(user_id)
        if not categories:
            await message.answer(
                "❌ Не выбраны категории для сканирования\n\n"
                "Используйте:\n"
                "/categories - посмотреть доступные категории\n"
                "/add_category <название> - добавить категорию"
            )
            return
    
    await auto_scan.start_auto_scan(user_id)
    
    mode_text = "все рынки" if settings['scan_mode'] == 'all' else f"категории: {', '.join(await db.get_scan_categories(user_id))}"
    await message.answer(
        f"🚀 Автосканирование запущено!\n\n"
        f"Режим: {mode_text}\n"
        f"Интервал: {settings['scan_interval']} сек\n"
        f"Дедупликация: {settings['dedup_hours']} ч"
    )

@router.message(Command("auto_scan_stop"))
async def cmd_auto_scan_stop(message: Message, db: Database, auto_scan: AutoScanService):
    """Обработчик команды /auto_scan_stop"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    settings = await db.get_auto_scan_settings(user_id)
    
    if not settings['is_enabled']:
        await message.answer("ℹ️ Автосканирование уже остановлено")
        return
    
    await auto_scan.stop_auto_scan(user_id)
    await message.answer("⏸️ Автосканирование остановлено")

@router.message(Command("auto_scan_status"))
async def cmd_auto_scan_status(message: Message, db: Database):
    """Обработчик команды /auto_scan_status"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    settings = await db.get_auto_scan_settings(user_id)
    filters = await db.get_filters(user_id)
    
    status = "активно ✅" if settings['is_enabled'] else "остановлено ⏸️"
    mode = "все рынки" if settings['scan_mode'] == 'all' else "по категориям"
    
    text = (
        "📊 Статус автосканирования:\n\n"
        f"• Состояние: {status}\n"
        f"• Режим: {mode}\n"
        f"• Интервал: {settings['scan_interval']} сек\n"
        f"• Дедупликация: {settings['dedup_hours']} ч\n"
        f"• Фильтров: {len(filters)}\n"
    )
    
    if settings['scan_mode'] == 'categories':
        categories = await db.get_scan_categories(user_id)
        text += f"• Категорий: {len(categories)}\n"
        if categories:
            text += f"\nКатегории:\n"
            for cat in categories[:5]:
                text += f"  - {cat}\n"
            if len(categories) > 5:
                text += f"  ... и ещё {len(categories) - 5}\n"
    
    await message.answer(text)

@router.message(Command("auto_scan_mode"))
async def cmd_auto_scan_mode(message: Message, db: Database):
    """Обработчик команды /auto_scan_mode"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /auto_scan_mode <all|categories>\n\n"
            "Примеры:\n"
            "/auto_scan_mode all - сканировать все рынки\n"
            "/auto_scan_mode categories - сканировать выбранные категории"
        )
        return
    
    mode = args[1].lower()
    if mode not in ['all', 'categories']:
        await message.answer("❌ Режим должен быть 'all' или 'categories'")
        return
    
    await db.set_auto_scan_settings(user_id, scan_mode=mode)
    
    mode_text = "все рынки" if mode == 'all' else "по категориям"
    await message.answer(f"✅ Режим сканирования установлен: {mode_text}")

@router.message(Command("auto_scan_interval"))
async def cmd_auto_scan_interval(message: Message, db: Database):
    """Обработчик команды /auto_scan_interval"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /auto_scan_interval <секунды>\n\n"
            "Примеры:\n"
            "/auto_scan_interval 60 - проверять каждую минуту\n"
            "/auto_scan_interval 300 - проверять каждые 5 минут"
        )
        return
    
    try:
        interval = int(args[1])
        if interval < 10:
            await message.answer("❌ Интервал должен быть не менее 10 секунд")
            return
        
        await db.set_auto_scan_settings(user_id, scan_interval=interval)
        await message.answer(f"✅ Интервал сканирования установлен: {interval} сек")
    
    except ValueError:
        await message.answer("❌ Неверное значение. Укажите число секунд")

@router.message(Command("auto_scan_dedup"))
async def cmd_auto_scan_dedup(message: Message, db: Database):
    """Обработчик команды /auto_scan_dedup"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /auto_scan_dedup <часы>\n\n"
            "Примеры:\n"
            "/auto_scan_dedup 1 - не повторять уведомления чаще раза в час\n"
            "/auto_scan_dedup 24 - не повторять уведомления чаще раза в сутки"
        )
        return
    
    try:
        hours = int(args[1])
        if hours < 0:
            await message.answer("❌ Количество часов должно быть положительным")
            return
        
        await db.set_auto_scan_settings(user_id, dedup_hours=hours)
        await message.answer(f"✅ Время дедупликации установлено: {hours} ч")
    
    except ValueError:
        await message.answer("❌ Неверное значение. Укажите число часов")

@router.message(Command("categories"))
async def cmd_categories(message: Message, api: PolymarketAPI):
    """Обработчик команды /categories"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    await message.answer("🔍 Загружаю список категорий...")
    
    try:
        categories = await api.get_all_unique_categories()
        
        if not categories:
            await message.answer("❌ Не удалось загрузить категории")
            return
        
        text = f"📋 Доступные категории ({len(categories)}):\n\n"
        
        # Показываем первые 20 категорий
        for i, cat in enumerate(categories[:20], 1):
            text += f"{i}. {cat}\n"
        
        if len(categories) > 20:
            text += f"\n... и ещё {len(categories) - 20} категорий\n"
        
        text += "\nДля добавления категории:\n/add_category <название>"
        
        await message.answer(text)
    
    except Exception as e:
        logger.error(f"Error in categories command: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(Command("add_category"))
async def cmd_add_category(message: Message, db: Database):
    """Обработчик команды /add_category"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /add_category <название>\n\n"
            "Примеры:\n"
            "/add_category Politics\n"
            "/add_category Bitcoin hits $1m\n\n"
            "Посмотреть доступные категории:\n/categories"
        )
        return
    
    category = args[1].strip()
    success = await db.add_scan_category(user_id, category)
    
    if success:
        await message.answer(f"✅ Категория добавлена: {category}")
    else:
        await message.answer(f"❌ Категория уже добавлена или ошибка")

@router.message(Command("remove_category"))
async def cmd_remove_category(message: Message, db: Database):
    """Обработчик команды /remove_category"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /remove_category <название>")
        return
    
    category = args[1].strip()
    success = await db.remove_scan_category(user_id, category)
    
    if success:
        await message.answer(f"✅ Категория удалена: {category}")
    else:
        await message.answer(f"❌ Категория не найдена")

@router.message(Command("my_categories"))
async def cmd_my_categories(message: Message, db: Database):
    """Обработчик команды /my_categories"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    categories = await db.get_scan_categories(user_id)
    
    if not categories:
        await message.answer(
            "📋 У вас нет выбранных категорий\n\n"
            "Добавьте категорию:\n/add_category <название>"
        )
        return
    
    text = f"📋 Ваши категории ({len(categories)}):\n\n"
    buttons = []
    
    for i, cat in enumerate(categories, 1):
        text += f"{i}. {cat}\n"
        
        # Добавляем кнопку удаления для каждой категории
        buttons.append([InlineKeyboardButton(
            text=f"🗑️ Удалить {cat}",
            callback_data=f"remove_category:{cat}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)

# ============================================================================
# TEXT HANDLERS (для Reply Keyboard кнопок)
# ============================================================================

@router.message(F.text == "🔍 Поиск")
async def btn_search(message: Message):
    """Обработчик кнопки Поиск"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    await message.answer(
        "🔍 Поиск рынков\n\n"
        "Используйте команду:\n"
        "/search <ключевые слова>\n\n"
        "Пример:\n"
        "/search trump election"
    )

@router.message(F.text == "📊 Мои рынки")
async def btn_markets(message: Message, db: Database):
    """Обработчик кнопки Мои рынки"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    markets = await db.get_markets(user_id)
    
    if not markets:
        await message.answer("📊 У вас нет отслеживаемых рынков\n\nИспользуйте /search для поиска рынков")
        return
    
    text = f"📊 Ваши рынки ({len(markets)}/{MAX_MARKETS}):\n\n"
    for i, (slug, name) in enumerate(markets, 1):
        text += f"{i}. {name}\n🔗 {slug}\n\n"
    
    await message.answer(text)

@router.message(F.text == "🎯 Фильтры")
async def btn_filters(message: Message, db: Database):
    """Обработчик кнопки Фильтры"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    filters = await db.get_filters(user_id)
    
    if not filters:
        await message.answer(
            "🎯 У вас нет активных фильтров\n\n"
            "Установите фильтр командой:\n"
            "/set_filter <type> <value>\n\n"
            "Доступные типы:\n"
            "• min_spread - минимальный спред (%)\n"
            "• max_spread - максимальный спред (%)\n"
            "• min_volume - минимальный объём ($)\n"
            "• max_volume - максимальный объём ($)\n"
            "• min_liquidity - минимальная ликвидность ($)"
        )
        return
    
    text = "🎯 Активные фильтры:\n\n"
    for filter_id, filter_type, filter_value in filters:
        text += f"ID {filter_id}: {filter_type} = {filter_value}\n"
    
    text += "\n💡 Удалить фильтр: /remove_filter <id>"
    
    await message.answer(text)

@router.message(F.text == "🤖 Автоскан")
async def btn_autoscan(message: Message, db: Database):
    """Обработчик кнопки Автоскан"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    settings = await db.get_auto_scan_settings(user_id)
    
    status = "активно ✅" if settings['is_enabled'] else "остановлено ⏸️"
    
    text = (
        f"🤖 Автосканирование: {status}\n\n"
        f"⚙️ Настройки:\n"
        f"• Режим: {settings['scan_mode']}\n"
        f"• Интервал: {settings['interval']} сек\n"
        f"• Дедупликация: {settings['dedup_hours']} ч\n\n"
        "📝 Команды:\n"
        "/auto_scan_start - запустить\n"
        "/auto_scan_stop - остановить\n"
        "/auto_scan_status - подробный статус\n"
        "/auto_scan_mode <all|categories> - режим"
    )
    
    await message.answer(text)

@router.message(F.text == "📈 Статус")
async def btn_status(message: Message, db: Database):
    """Обработчик кнопки Статус"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    markets = await db.get_markets(user_id)
    is_active = await db.get_monitoring_state(user_id)
    filters = await db.get_filters(user_id)
    auto_scan_settings = await db.get_auto_scan_settings(user_id)
    
    status = "активен ✅" if is_active else "остановлен ⏸️"
    auto_scan_status = "активно ✅" if auto_scan_settings['is_enabled'] else "остановлено ⏸️"
    
    text = (
        "📈 Статус бота\n\n"
        "📊 Мониторинг конкретных рынков:\n"
        f"• Рынков: {len(markets)}/{MAX_MARKETS}\n"
        f"• Статус: {status}\n"
        f"• Фильтров: {len(filters)}\n"
        f"• Интервал: {MONITORING_INTERVAL} сек\n\n"
        "🤖 Автосканирование:\n"
        f"• Статус: {auto_scan_status}\n"
        f"• Режим: {auto_scan_settings['scan_mode']}\n"
        f"• Интервал: {auto_scan_settings['interval']} сек\n"
        f"• Дедупликация: {auto_scan_settings['dedup_hours']} ч"
    )
    
    await message.answer(text)

@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message):
    """Обработчик кнопки Помощь"""
    user_id = message.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await message.answer("❌ Access denied")
        return
    
    # Вызываем команду /help
    await cmd_help(message)

# ============================================================================
# CALLBACK HANDLERS (для Inline кнопок)
# ============================================================================

@router.callback_query(F.data.startswith("add_market:"))
async def callback_add_market(callback: CallbackQuery, db: Database, api: PolymarketAPI, monitoring: MonitoringService):
    """Обработчик callback для добавления рынка"""
    user_id = callback.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await callback.answer("❌ Access denied", show_alert=True)
        return
    
    # Извлекаем slug из callback_data
    slug = callback.data.split(":", 1)[1]
    
    try:
        # Проверяем лимит рынков
        markets_count = await db.get_markets_count(user_id)
        if markets_count >= MAX_MARKETS:
            await callback.answer(f"❌ Достигнут лимит рынков ({MAX_MARKETS})", show_alert=True)
            return
        
        # Получаем данные о рынке
        market_data = await api.get_market_by_slug(slug)
        if not market_data:
            await callback.answer("❌ Рынок не найден", show_alert=True)
            return
        
        market_name = market_data.get("question", "Unknown")
        
        # Добавляем рынок
        success = await db.add_market(user_id, slug, market_name)
        
        if not success:
            await callback.answer("❌ Этот рынок уже добавлен", show_alert=True)
            return
        
        # Запускаем мониторинг если не активен
        is_active = await db.get_monitoring_state(user_id)
        if not is_active:
            await db.set_monitoring_state(user_id, True)
            await monitoring.start_monitoring(user_id)
        
        await callback.answer("✅ Рынок добавлен и мониторинг запущен!", show_alert=True)
        
        # Обновляем сообщение
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ Рынок добавлен в мониторинг!",
            reply_markup=None
        )
        
    except Exception as e:
        logger.error(f"Error in callback_add_market: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("remove_market:"))
async def callback_remove_market(callback: CallbackQuery, db: Database, monitoring: MonitoringService):
    """Обработчик callback для удаления рынка"""
    user_id = callback.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await callback.answer("❌ Access denied", show_alert=True)
        return
    
    slug = callback.data.split(":", 1)[1]
    
    try:
        success = await db.remove_market(user_id, slug)
        
        if success:
            await callback.answer("✅ Рынок удалён", show_alert=True)
            
            # Проверяем, остались ли рынки
            markets_count = await db.get_markets_count(user_id)
            if markets_count == 0:
                await monitoring.stop_monitoring(user_id)
            
            # Обновляем сообщение
            await callback.message.edit_text(
                f"{callback.message.text}\n\n🗑️ Рынок удалён из мониторинга",
                reply_markup=None
            )
        else:
            await callback.answer("❌ Рынок не найден", show_alert=True)
    
    except Exception as e:
        logger.error(f"Error in callback_remove_market: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("remove_filter:"))
async def callback_remove_filter(callback: CallbackQuery, db: Database):
    """Обработчик callback для удаления фильтра"""
    user_id = callback.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await callback.answer("❌ Access denied", show_alert=True)
        return
    
    filter_id = int(callback.data.split(":", 1)[1])
    
    try:
        success = await db.remove_filter(user_id, filter_id)
        
        if success:
            await callback.answer("✅ Фильтр удалён", show_alert=True)
            
            # Обновляем список фильтров
            filters = await db.get_filters(user_id)
            
            if not filters:
                await callback.message.edit_text(
                    "🎯 Все фильтры удалены\n\nУстановите новый фильтр командой:\n/set_filter <type> <value>",
                    reply_markup=None
                )
            else:
                text = "🎯 Активные фильтры:\n\n"
                buttons = []
                
                for fid, ftype, fvalue in filters:
                    text += f"ID {fid}: {ftype} = {fvalue}\n"
                    buttons.append([InlineKeyboardButton(
                        text=f"🗑️ Удалить фильтр {fid}",
                        callback_data=f"remove_filter:{fid}"
                    )])
                
                buttons.append([InlineKeyboardButton(
                    text="🧹 Очистить все фильтры",
                    callback_data="clear_all_filters"
                )])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.answer("❌ Фильтр не найден", show_alert=True)
    
    except Exception as e:
        logger.error(f"Error in callback_remove_filter: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "clear_all_filters")
async def callback_clear_all_filters(callback: CallbackQuery, db: Database):
    """Обработчик callback для очистки всех фильтров"""
    user_id = callback.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await callback.answer("❌ Access denied", show_alert=True)
        return
    
    try:
        filters = await db.get_filters(user_id)
        
        for filter_id, _, _ in filters:
            await db.remove_filter(user_id, filter_id)
        
        await callback.answer("✅ Все фильтры удалены", show_alert=True)
        await callback.message.edit_text(
            "🎯 Все фильтры удалены\n\nУстановите новый фильтр командой:\n/set_filter <type> <value>",
            reply_markup=None
        )
    
    except Exception as e:
        logger.error(f"Error in callback_clear_all_filters: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "monitoring_start")
async def callback_monitoring_start(callback: CallbackQuery, db: Database, monitoring: MonitoringService):
    """Обработчик callback для запуска мониторинга"""
    user_id = callback.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await callback.answer("❌ Access denied", show_alert=True)
        return
    
    try:
        markets_count = await db.get_markets_count(user_id)
        
        if markets_count == 0:
            await callback.answer("❌ Нет рынков для мониторинга", show_alert=True)
            return
        
        await db.set_monitoring_state(user_id, True)
        await monitoring.start_monitoring(user_id)
        
        await callback.answer("✅ Мониторинг запущен", show_alert=True)
        
        # Обновляем сообщение
        await callback.message.edit_text(
            f"{callback.message.text}\n\n▶️ Мониторинг запущен",
            reply_markup=None
        )
    
    except Exception as e:
        logger.error(f"Error in callback_monitoring_start: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "monitoring_stop")
async def callback_monitoring_stop(callback: CallbackQuery, db: Database, monitoring: MonitoringService):
    """Обработчик callback для остановки мониторинга"""
    user_id = callback.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await callback.answer("❌ Access denied", show_alert=True)
        return
    
    try:
        await monitoring.stop_monitoring(user_id)
        await db.set_monitoring_state(user_id, False)
        
        await callback.answer("✅ Мониторинг остановлен", show_alert=True)
        
        # Обновляем сообщение
        await callback.message.edit_text(
            f"{callback.message.text}\n\n⏸️ Мониторинг остановлен",
            reply_markup=None
        )
    
    except Exception as e:
        logger.error(f"Error in callback_monitoring_stop: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("remove_category:"))
async def callback_remove_category(callback: CallbackQuery, db: Database):
    """Обработчик callback для удаления категории"""
    user_id = callback.from_user.id
    
    if user_id != ALLOWED_USER_ID:
        await callback.answer("❌ Access denied", show_alert=True)
        return
    
    category = callback.data.split(":", 1)[1]
    
    try:
        success = await db.remove_scan_category(user_id, category)
        
        if success:
            await callback.answer("✅ Категория удалена", show_alert=True)
            
            # Обновляем список категорий
            categories = await db.get_scan_categories(user_id)
            
            if not categories:
                await callback.message.edit_text(
                    "📋 Все категории удалены\n\nДобавьте категорию:\n/add_category <название>",
                    reply_markup=None
                )
            else:
                text = f"📋 Ваши категории ({len(categories)}):\n\n"
                buttons = []
                
                for i, cat in enumerate(categories, 1):
                    text += f"{i}. {cat}\n"
                    buttons.append([InlineKeyboardButton(
                        text=f"🗑️ Удалить {cat}",
                        callback_data=f"remove_category:{cat}"
                    )])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.answer("❌ Категория не найдена", show_alert=True)
    
    except Exception as e:
        logger.error(f"Error in callback_remove_category: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Главная функция"""
    logger.info("Starting Polymarket Spread Monitor Bot...")
    
    # Инициализация базы данных
    db = Database()
    await db.init_db()
    
    # Создание HTTP сессии с прокси
    connector = ProxyConnector.from_url(PROXY_URL)
    http_session = aiohttp.ClientSession(connector=connector)
    
    # Инициализация API клиента
    api = PolymarketAPI(http_session)
    
    # Создание бота с прокси
    bot_session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=bot_session)
    
    # Инициализация сервиса мониторинга
    monitoring = MonitoringService(bot, db, api)
    
    # Инициализация сервиса автосканирования
    auto_scan = AutoScanService(bot, db, api)
    
    # Создание диспетчера
    dp = Dispatcher()
    dp.include_router(router)
    
    # Передача зависимостей в хендлеры
    dp["db"] = db
    dp["api"] = api
    dp["monitoring"] = monitoring
    dp["auto_scan"] = auto_scan
    
    # Восстановление мониторинга после перезапуска
    is_active = await db.get_monitoring_state(ALLOWED_USER_ID)
    markets_count = await db.get_markets_count(ALLOWED_USER_ID)
    if is_active and markets_count > 0:
        await monitoring.start_monitoring(ALLOWED_USER_ID)
        logger.info(f"Restored monitoring for user {ALLOWED_USER_ID}")
    
    # Восстановление автосканирования после перезапуска
    auto_scan_settings = await db.get_auto_scan_settings(ALLOWED_USER_ID)
    if auto_scan_settings['is_enabled']:
        await auto_scan.start_auto_scan(ALLOWED_USER_ID)
        logger.info(f"Restored auto scan for user {ALLOWED_USER_ID}")
    
    try:
        logger.info("Bot started successfully!")
        await dp.start_polling(bot)
    finally:
        await http_session.close()
        await bot.session.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
