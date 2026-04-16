# 📤 Инструкция по загрузке проекта на GitHub

## Шаг 1: Установка Git (если не установлен)

### Windows:
1. Скачайте Git с официального сайта: https://git-scm.com/download/win
2. Запустите установщик
3. Используйте настройки по умолчанию
4. После установки перезапустите командную строку

### Проверка установки:
```bash
git --version
```

---

## Шаг 2: Настройка Git (первый раз)

Откройте командную строку и выполните:

```bash
git config --global user.name "Ваше Имя"
git config --global user.email "your.email@example.com"
```

---

## Шаг 3: Создание репозитория на GitHub

1. Откройте https://github.com
2. Войдите в свой аккаунт (или создайте новый)
3. Нажмите кнопку "+" в правом верхнем углу
4. Выберите "New repository"
5. Заполните форму:
   - **Repository name**: `polymarket-spread-monitor`
   - **Description**: `Telegram bot for monitoring Polymarket spreads`
   - **Visibility**: Public или Private (на ваш выбор)
   - ❌ НЕ ставьте галочку "Initialize this repository with a README"
6. Нажмите "Create repository"

---

## Шаг 4: Инициализация локального репозитория

Откройте командную строку в папке проекта:

```bash
cd "C:\Users\Yarik\OneDrive\Документы\vibe-coding-project\trying-spread"
```

Выполните команды:

```bash
# Инициализация git репозитория
git init

# Добавление всех файлов
git add .

# Создание первого коммита
git commit -m "Initial commit: Polymarket Spread Monitor Bot"

# Переименование ветки в main (если нужно)
git branch -M main
```

---

## Шаг 5: Связывание с GitHub и загрузка

Замените `YOUR_USERNAME` на ваше имя пользователя GitHub:

```bash
# Добавление удалённого репозитория
git remote add origin https://github.com/YOUR_USERNAME/polymarket-spread-monitor.git

# Загрузка на GitHub
git push -u origin main
```

**Важно:** При первой загрузке GitHub может запросить авторизацию. Используйте:
- Personal Access Token (рекомендуется)
- GitHub Desktop
- SSH ключ

---

## Шаг 6: Создание Personal Access Token (если нужно)

Если GitHub запрашивает пароль:

1. Откройте https://github.com/settings/tokens
2. Нажмите "Generate new token" → "Generate new token (classic)"
3. Заполните:
   - **Note**: `Polymarket Bot`
   - **Expiration**: 90 days (или больше)
   - **Scopes**: отметьте `repo`
4. Нажмите "Generate token"
5. **СКОПИРУЙТЕ токен** (он больше не будет показан!)
6. Используйте токен вместо пароля при `git push`

---

## Альтернативный способ: GitHub Desktop

Если командная строка кажется сложной:

1. Скачайте GitHub Desktop: https://desktop.github.com/
2. Установите и войдите в аккаунт
3. File → Add Local Repository
4. Выберите папку проекта
5. Нажмите "Publish repository"
6. Выберите имя и видимость
7. Нажмите "Publish"

---

## Шаг 7: Проверка

Откройте в браузере:
```
https://github.com/YOUR_USERNAME/polymarket-spread-monitor
```

Вы должны увидеть все файлы проекта!

---

## 📝 Что будет загружено:

```
✅ bot.py              - основной код бота
✅ requirements.txt    - зависимости
✅ start_bot.bat       - автозапуск
✅ .env.example        - пример конфигурации
✅ README.md          - документация
✅ QUICKSTART.md      - быстрый старт
✅ CHANGELOG.md       - история изменений
✅ PROJECT_SUMMARY.md - техническая сводка
✅ .gitignore         - исключения для git

❌ bot.db             - база данных (игнорируется)
❌ bot.log            - логи (игнорируются)
❌ test_*.py          - тестовые скрипты (игнорируются)
```

---

## 🔒 Безопасность

**ВАЖНО:** Файл `.env.example` содержит ваши реальные данные!

Перед загрузкой на GitHub:

1. Откройте `.env.example`
2. Замените реальные данные на примеры:

```env
BOT_TOKEN=your_bot_token_here
PROXY_URL=http://user:pass@host:port
ALLOWED_USER_ID=your_telegram_user_id
```

3. Сохраните файл
4. Выполните:
```bash
git add .env.example
git commit -m "Update .env.example with placeholders"
git push
```

**Или** удалите `.env.example` из репозитория:
```bash
git rm .env.example
git commit -m "Remove .env.example with sensitive data"
git push
```

---

## 🔄 Обновление репозитория в будущем

После внесения изменений:

```bash
git add .
git commit -m "Описание изменений"
git push
```

---

## ❓ Проблемы и решения

### Ошибка: "git is not recognized"
**Решение:** Установите Git (см. Шаг 1)

### Ошибка: "Permission denied"
**Решение:** Используйте Personal Access Token вместо пароля

### Ошибка: "remote origin already exists"
**Решение:** 
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/polymarket-spread-monitor.git
```

### Ошибка: "failed to push some refs"
**Решение:**
```bash
git pull origin main --rebase
git push origin main
```

---

## 📞 Нужна помощь?

- GitHub Docs: https://docs.github.com
- Git Tutorial: https://git-scm.com/docs/gittutorial
- GitHub Desktop: https://desktop.github.com/

---

**Готово! Ваш проект будет доступен на GitHub! 🎉**
