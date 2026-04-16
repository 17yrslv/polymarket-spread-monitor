# 🚀 Быстрая загрузка на GitHub

## Вариант 1: Автоматический (рекомендуется)

1. **Установите Git** (если не установлен):
   - Скачайте: https://git-scm.com/download/win
   - Установите с настройками по умолчанию
   - Перезапустите командную строку

2. **Создайте репозиторий на GitHub**:
   - Откройте: https://github.com/new
   - Название: `polymarket-spread-monitor`
   - Описание: `Telegram bot for monitoring Polymarket spreads`
   - Visibility: Public или Private
   - ❌ НЕ добавляйте README, .gitignore или лицензию
   - Нажмите "Create repository"

3. **Запустите автоматическую загрузку**:
   - Дважды кликните на `upload_to_github.bat`
   - Следуйте инструкциям на экране
   - Введите URL вашего репозитория когда попросят

---

## Вариант 2: Ручной (через командную строку)

Откройте командную строку в папке проекта и выполните:

```bash
# 1. Инициализация
git init
git add .
git commit -m "Initial commit: Polymarket Spread Monitor Bot"
git branch -M main

# 2. Связывание с GitHub (замените YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/polymarket-spread-monitor.git

# 3. Загрузка
git push -u origin main
```

---

## Вариант 3: GitHub Desktop (самый простой)

1. Скачайте: https://desktop.github.com/
2. Установите и войдите в аккаунт
3. File → Add Local Repository
4. Выберите папку проекта
5. Нажмите "Publish repository"
6. Готово!

---

## ⚠️ ВАЖНО: Безопасность

Файл `.env.example` уже обновлён и не содержит реальных данных.

Но в файле `bot.py` (строки 28-30) есть ваши реальные данные:
- Bot Token
- Proxy
- User ID

**Рекомендации:**
1. Если репозиторий **Private** - можно оставить как есть
2. Если репозиторий **Public** - замените данные в bot.py на переменные окружения

---

## 🔑 Personal Access Token

Если GitHub запрашивает пароль при `git push`:

1. Откройте: https://github.com/settings/tokens
2. "Generate new token" → "Generate new token (classic)"
3. Note: `Polymarket Bot`
4. Expiration: 90 days
5. Scopes: отметьте `repo`
6. "Generate token"
7. **СКОПИРУЙТЕ токен!**
8. Используйте токен вместо пароля

---

## ✅ Проверка

После загрузки откройте:
```
https://github.com/YOUR_USERNAME/polymarket-spread-monitor
```

Вы должны увидеть все файлы!

---

## 📞 Нужна помощь?

Смотрите подробную инструкцию: `GITHUB_UPLOAD.md`
