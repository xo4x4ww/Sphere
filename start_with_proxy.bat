@echo off
title Sphere Bot (с прокси)
echo ========================================
echo    Sphere Bot - Запуск с поддержкой прокси
echo ========================================
echo.

echo [1] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не установлен
    pause
    exit /b 1
)
echo OK

echo [2] Установка зависимостей (включая прокси)...
python -m pip install -q httpx[socks] python-telegram-bot python-dotenv
echo OK

echo [3] Запуск бота...
echo.
echo --------------------------------------------------
echo Если используете прокси - он будет применён
echo Для отключения прокси - удалите PROXY_URL из .env
echo --------------------------------------------------
echo.

python bot_with_proxy.py

pause