# Исправление ошибки KeyError: 'id' в команде /filters

**Дата:** 2026-04-17  
**Статус:** ✅ ИСПРАВЛЕНО

---

## Проблема

При использовании команды `/filters` возникала ошибка:

```
KeyError: 'id'
at line 1629: filter_id = filter_item["id"]
```

## Причина

Метод `Database.get_filters()` возвращал только `filter_type` и `filter_value`, но не возвращал `id` фильтра, который необходим для:
- Отображения ID в списке фильтров
- Удаления фильтра по ID через callback кнопки

## Исправления

### 1. Обновлен метод `get_filters()` в классе Database

**Было:**
```python
cursor = await db.execute(
    "SELECT filter_type, filter_value FROM filters WHERE user_id = ?",
    (user_id,)
)
```

**Стало:**
```python
cursor = await db.execute(
    "SELECT id, filter_type, filter_value FROM filters WHERE user_id = ?",
    (user_id,)
)
```

### 2. Добавлен метод `remove_filter()` в классе Database

Добавлен новый метод для удаления фильтра по ID:

```python
async def remove_filter(self, user_id: int, filter_id: int) -> bool:
    """Удалить фильтр по ID"""
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            "DELETE FROM filters WHERE user_id = ? AND id = ?",
            (user_id, filter_id)
        )
        await db.commit()
        return cursor.rowcount > 0
```

### 3. Исправлен callback `callback_remove_filter`

**Было:**
```python
for fid, ftype, fvalue in filters:
    text += f"ID {fid}: {ftype} = {fvalue}\n"
```

**Стало:**
```python
for filter_item in filters:
    fid = filter_item["id"]
    ftype = filter_item["filter_type"]
    fvalue = filter_item["filter_value"]
    
    if ftype == "spread_min":
        text += f"ID {fid}: Минимальный спред: {fvalue}%\n"
    elif ftype == "volume_min":
        text += f"ID {fid}: Минимальный объём: ${fvalue}\n"
    # ... и т.д.
```

### 4. Исправлен callback `callback_clear_all_filters`

**Было:**
```python
for filter_id, _, _ in filters:
    await db.remove_filter(user_id, filter_id)
```

**Стало:**
```python
for filter_item in filters:
    await db.remove_filter(user_id, filter_item["id"])
```

## Тестирование

Создан тестовый скрипт `test_filters_fix.py` для проверки:

```bash
python test_filters_fix.py
```

**Результат:** ✅ Все тесты пройдены успешно

Проверено:
- Добавление фильтров
- Получение списка фильтров с ID
- Удаление фильтра по ID
- Очистка всех фильтров

## Затронутые файлы

- `bot.py` - исправлены методы Database и callback обработчики

## Команды для проверки

После запуска бота проверьте:

```
/set_filter spread_min 2
/set_filter volume_min 100000
/set_filter trade_frequency_min 10 5
/filters
```

Должен отобразиться список фильтров с ID и кнопками для удаления.

## Статус

✅ **ИСПРАВЛЕНО И ПРОТЕСТИРОВАНО**

Команда `/filters` теперь работает корректно:
- Отображает все фильтры с ID
- Показывает читаемое описание каждого фильтра
- Кнопки удаления работают
- Очистка всех фильтров работает

---

**Версия:** 1.1.1  
**Дата исправления:** 2026-04-17
