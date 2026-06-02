@echo off
chcp 65001 >nul
title Sphere Bot
echo ========================================
echo    Sphere Bot - Запуск
echo ========================================
echo.

echo [1] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не установлен
    pause
    exit /b 1
)
echo OK: Python найден

echo [2] Установка зависимостей...
python -m pip install --quiet python-telegram-bot python-dotenv
echo OK

echo [3] Запуск бота...
echo.

python bot.py

pause