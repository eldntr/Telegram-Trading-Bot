# config.py
import os
import json
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

# --- Konfigurasi Sistem ---
API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER")
TARGET_CHAT_ID = int(os.getenv("TELEGRAM_TARGET_CHAT_ID", 0))
SESSION_NAME = "trading_bot_session"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = "trading_bot_db"

def load_user_config(path: str = "user_config.json") -> Dict[str, Any]:
    """Memuat konfigurasi spesifik pengguna dari file JSON."""
    try:
        with open(path, 'r') as f:
            print(f"Konfigurasi pengguna berhasil dimuat dari {path}")
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"FATAL: Gagal memuat atau parse file '{path}'. Error: {e}")
        # Keluar dari program atau berikan default config yang aman
        raise SystemExit(f"Error loading user configuration: {e}")