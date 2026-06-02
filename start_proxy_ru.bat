@echo off
chcp 65001 >nul
title Sphere Bot (c прокси)
echo ========================================
echo    Sphere Bot - Запуск с прокси
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

echo [2] Установка зависимостей...
python -m pip install --quiet httpx[socks] python-telegram-bot python-dotenv
echo OK

echo [3] Запуск бота...
echo.

python bot_with_proxy.py

pause