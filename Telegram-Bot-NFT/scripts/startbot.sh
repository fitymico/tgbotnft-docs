#!/bin/bash

WORKDIR="../Gift_API/src"
FILENAME="giftBot.ts"

if [ -d "$WORKDIR" ]; then
    echo "Entering working directory: $WORKDIR"
    cd "$WORKDIR" || exit 1
else
    echo "No folder with name: $WORKDIR" && exit 1
fi

if [ -f "$FILENAME" ]; then
    echo "Starting scaning: $FILENAME"
    npm run dev
else
    echo "No file name: $FILENAME" && exit 1
fi