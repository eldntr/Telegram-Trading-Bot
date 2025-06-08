#!/bin/sh
# Auto Trade Bot/run_bot.sh
set -e

echo "--- Starting Bot Cycle ---"

python main.py autoloop --duration 0 --delay 300 --limit 20