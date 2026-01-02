#!/bin/bash

# Определяем корневую директорию проекта
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WORKDIR="$PROJECT_ROOT/Gift_API"
LOGFILE="$PROJECT_ROOT/data/giftbot.log"

# Загружаем переменные окружения
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

if [ -d "$WORKDIR" ]; then
    echo "Entering working directory: $WORKDIR"
    cd "$WORKDIR" || exit 1
else
    echo "No folder with name: $WORKDIR" && exit 1
fi

echo "Starting Gift API bot..."
echo "Logs: $LOGFILE"

# Определяем команду запуска:
# - В Docker или если dist уже скомпилирован: npm start
# - Иначе: npm run dev (компиляция + запуск)
if [ -f "$WORKDIR/dist/giftBot.js" ]; then
    echo "Using pre-compiled dist..."
    NPM_CMD="npm start"
else
    echo "Compiling TypeScript..."
    NPM_CMD="npm run dev"
fi

# Запуск в фоне с перенаправлением логов
nohup $NPM_CMD >> "$LOGFILE" 2>&1 &

echo "Gift API bot started (PID: $!)"
echo $! > "$PROJECT_ROOT/data/giftbot.pid"