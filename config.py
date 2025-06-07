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

# --- BARU: Konfigurasi Trailing Stop Loss ---
# Ubah string "True" dari .env menjadi boolean True
TRAILING_ENABLED = os.getenv("TRAILING_ENABLED", "False").lower() in ('true', '1', 't')
# Level TP minimum untuk memulai trailing (misal: 1 untuk mulai dari TP1)
MIN_TRAILING_TP_LEVEL = int(os.getenv("MIN_TRAILING_TP_LEVEL", 1))
# Persentase pemicu di atas harga TP (0.005 = 0.5%)
TRAILING_TRIGGER_PERCENTAGE = float(os.getenv("TRAILING_TRIGGER_PERCENTAGE", 0.005))