#!/bin/sh
# Auto Trade Bot/run_bot.sh (Versi Perbaikan)
set -e

echo "--- Starting Bot ---"
# Langsung jalankan autoloop dengan argumen untuk fetch awal yang besar
python main.py autoloop --duration 0 --delay 300 --limit 20 --initial-limit 100