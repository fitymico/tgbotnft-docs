#!/bin/bash

# Определяем корневую директорию проекта
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PIDFILE="$PROJECT_ROOT/data/giftbot.pid"
FILENAME="dist/giftBot.js"

# Останавливаем по PID файлу
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Останавливаем Gift API бот (PID: $PID)..."
        kill "$PID"
        sleep 1
        if kill -0 "$PID" 2>/dev/null; then
            echo "Принудительное завершение..."
            kill -9 "$PID"
        fi
        echo "Gift API бот остановлен"
    else
        echo "Процесс $PID уже не запущен"
    fi
    rm -f "$PIDFILE"
fi

# Также убиваем оставшиеся процессы giftBot.js
if pgrep -f "$FILENAME" > /dev/null; then
    echo "Убиваем оставшиеся процессы $FILENAME..."
    pkill -f "$FILENAME"
    sleep 1
    if pgrep -f "$FILENAME" > /dev/null; then
        echo "Принудительное завершение..."
        pkill -9 -f "$FILENAME"
    fi
    echo "Все процессы $FILENAME остановлены"
else
    echo "$FILENAME не выполняется; нечего останавливать"
fi
