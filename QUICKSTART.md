# 🚀 Быстрый старт

## Установка и запуск за 3 шага:

### 1. Установите зависимости
```bash
pip install -r requirements.txt
```

### 2. Запустите бота
Дважды кликните на `start_bot.bat` или выполните:
```bash
python bot.py
```

### 3. Откройте Telegram и начните работу
Найдите вашего бота в Telegram и отправьте команду:
```
/start
```

## Первые шаги:

### Найти и добавить рынок (рекомендуется):
```
/search Trump
/set_market trump-out-as-president-before-gta-vi-846
```

### Или добавить рынок напрямую по slug:
```
/set_market russia-ukraine-ceasefire-before-gta-vi-554
```

### Посмотреть список рынков:
```
/markets
```

### Установить фильтр по спреду:
```
/set_filter spread_min 1.5
```

### Проверить статус:
```
/status
```

## Как найти рынок?

### Способ 1: Команда /search (проще всего!)
```
/search Trump
/search Ukraine
/search Bitcoin
```

### Способ 2: Скопировать slug с сайта

1. Откройте https://polymarket.com
2. Найдите интересующий рынок
3. Скопируйте последнюю часть URL

Пример:
```
URL: https://polymarket.com/event/russia-ukraine-ceasefire-before-gta-vi-554
Slug: russia-ukraine-ceasefire-before-gta-vi-554
```

## Полная документация

Смотрите [README.md](README.md) для подробной информации о всех командах и возможностях.

---

**Готово! Бот будет отправлять обновления каждые 10 секунд. 🎉**
