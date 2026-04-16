@echo off
chcp 65001 >nul
echo ========================================
echo   GitHub Upload Helper
echo ========================================
echo.

REM Проверка установки Git
where git >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git не установлен!
    echo.
    echo Пожалуйста, установите Git:
    echo 1. Откройте: https://git-scm.com/download/win
    echo 2. Скачайте и установите Git
    echo 3. Перезапустите эту программу
    echo.
    pause
    exit /b 1
)

echo [OK] Git установлен
echo.

REM Проверка конфигурации Git
git config user.name >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [SETUP] Настройка Git...
    echo.
    set /p USERNAME="Введите ваше имя для Git: "
    set /p EMAIL="Введите ваш email для Git: "
    git config --global user.name "%USERNAME%"
    git config --global user.email "%EMAIL%"
    echo [OK] Git настроен
    echo.
)

REM Инициализация репозитория
echo [STEP 1] Инициализация Git репозитория...
git init
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Не удалось инициализировать репозиторий
    pause
    exit /b 1
)
echo [OK] Репозиторий инициализирован
echo.

REM Добавление файлов
echo [STEP 2] Добавление файлов...
git add .
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Не удалось добавить файлы
    pause
    exit /b 1
)
echo [OK] Файлы добавлены
echo.

REM Создание коммита
echo [STEP 3] Создание коммита...
git commit -m "Initial commit: Polymarket Spread Monitor Bot"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Не удалось создать коммит
    pause
    exit /b 1
)
echo [OK] Коммит создан
echo.

REM Переименование ветки
echo [STEP 4] Переименование ветки в main...
git branch -M main
echo [OK] Ветка переименована
echo.

REM Запрос URL репозитория
echo [STEP 5] Связывание с GitHub...
echo.
echo Создайте репозиторий на GitHub:
echo 1. Откройте: https://github.com/new
echo 2. Название: polymarket-spread-monitor
echo 3. НЕ добавляйте README, .gitignore или лицензию
echo 4. Нажмите "Create repository"
echo.
set /p REPO_URL="Введите URL вашего репозитория (например: https://github.com/username/polymarket-spread-monitor.git): "

git remote add origin %REPO_URL%
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Remote уже существует, обновляем...
    git remote set-url origin %REPO_URL%
)
echo [OK] Репозиторий связан
echo.

REM Загрузка на GitHub
echo [STEP 6] Загрузка на GitHub...
echo.
echo ВАЖНО: GitHub может запросить авторизацию
echo Используйте Personal Access Token вместо пароля!
echo.
echo Создать токен: https://github.com/settings/tokens
echo.
pause

git push -u origin main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Не удалось загрузить на GitHub
    echo.
    echo Возможные причины:
    echo - Неправильный URL репозитория
    echo - Нужен Personal Access Token
    echo - Проблемы с авторизацией
    echo.
    echo Инструкции: см. GITHUB_UPLOAD.md
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Успешно загружено на GitHub!
echo ========================================
echo.
echo Ваш репозиторий: %REPO_URL%
echo.
pause
