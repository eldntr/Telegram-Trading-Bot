# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi Telegram
API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER")
TARGET_CHAT_ID = int(os.getenv("TELEGRAM_TARGET_CHAT_ID", 0))
SESSION_NAME = "trading_bot_session"

# Konfigurasi Binance
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Konfigurasi Trading
USDT_AMOUNT_PER_TRADE = float(os.getenv("USDT_AMOUNT_PER_TRADE", 11.0))

# Konfigurasi MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = "trading_bot_db"

# Konfigurasi Trailing Stop Loss
TRAILING_ENABLED = os.getenv("TRAILING_ENABLED", "False").lower() in ('true', '1', 't')
MIN_TRAILING_TP_LEVEL = int(os.getenv("MIN_TRAILING_TP_LEVEL", 1))
TRAILING_TRIGGER_PERCENTAGE = float(os.getenv("TRAILING_TRIGGER_PERCENTAGE", 0.005))

# Konfigurasi Posisi Macet
STUCK_TRADE_ENABLED = os.getenv("STUCK_TRADE_ENABLED", "False").lower() in ('true', '1', 't')
STUCK_TRADE_DURATION_HOURS = int(os.getenv("STUCK_TRADE_DURATION_HOURS", 6))

# --- BARU: Konfigurasi Prioritas Risiko ---
PRIORITIZE_NORMAL_RISK = os.getenv("PRIORITIZE_NORMAL_RISK", "False").lower() in ('true', '1', 't')

# --- BARU: Konfigurasi Validitas Waktu Sinyal ---
FILTER_OLD_SIGNALS_ENABLED = os.getenv("FILTER_OLD_SIGNALS_ENABLED", "True").lower() in ('true', '1', 't')
SIGNAL_VALIDITY_MINUTES = int(os.getenv("SIGNAL_VALIDITY_MINUTES", 30))