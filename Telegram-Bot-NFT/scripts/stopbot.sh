#!/bin/bash

FILENAME="nftbot.py"
is_working=$(ps aux | grep "$FILENAME" | grep -v grep)

if pgrep -f "$FILENAME" > /dev/null; then
    echo "Убиваем процесс Telethon бота..."
    pkill -f "$FILENAME"
    sleep 1
    if pgrep -f "$FILENAME" > /dev/null; then
        echo "Процесс не остановился, принудительное завершение..."
        pkill -9 -f "$FILENAME"
    fi
    
    echo "Процесс убит"
else
    echo "$FILENAME не выполняется; нечего останавливать"
fi
