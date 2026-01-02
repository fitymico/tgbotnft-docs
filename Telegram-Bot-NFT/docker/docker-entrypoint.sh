#!/bin/bash
set -e

echo "🚀 Запуск Telegram Gift Bot..."

# Проверяем наличие .env переменных
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Ошибка: BOT_TOKEN не задан"
    exit 1
fi

if [ -z "$ADMIN_ID" ]; then
    echo "❌ Ошибка: ADMIN_ID не задан"
    exit 1
fi

if [ -z "$API_ID" ]; then
    echo "❌ Ошибка: API_ID не задан"
    exit 1
fi

if [ -z "$API_HASH" ]; then
    echo "❌ Ошибка: API_HASH не задан"
    exit 1
fi

echo "✅ Все переменные окружения заданы"

# Создаём директорию data если её нет
mkdir -p /app/data

cd /app/Message_Bot

echo "🤖 Запуск Telegram бота..."
exec python talkbot.py
