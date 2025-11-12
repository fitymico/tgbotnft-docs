#!/bin/bash

WORKDIR="../NFT_Bot"
FILENAME="nftbot.py"

if [ -d "$WORKDIR" ]; then
    echo "Entering working directory: $WORKDIR"
    cd "$WORKDIR" || exit 1
else
    echo "No folder with name: $WORKDIR" && exit 1
fi

if [ -f "$FILENAME" ]; then
    echo "Starting bot: $FILENAME"
    python3 "$FILENAME"
else
    echo "No file name: $FILENAME" && exit 1
fi