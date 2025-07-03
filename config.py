# eldntr/telegram-trading-bot/Telegram-Trading-Bot-prioritize-normal-risk/config.py

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

# --- Konfigurasi Trailing Stop Loss Dinamis ---
TRAILING_ENABLED = os.getenv("TRAILING_ENABLED", "True").lower() in ('true', '1', 't')
TRAILING_CONFIG = {
    "1": 0,
    "2": 1,
    "3": 2,
    "4": 3,
}

# --- BARU: Konfigurasi untuk Strategi Hybrid Partial TP ---
# Membaca persentase penjualan dari file .env. Nilai dalam desimal (misal: 25% -> 0.25)
PARTIAL_TP_CONFIG = {
    1: float(os.getenv("PARTIAL_TP1_PERCENT", "0")) / 100,
    2: float(os.getenv("PARTIAL_TP2_PERCENT", "0")) / 100,
    3: float(os.getenv("PARTIAL_TP3_PERCENT", "0")) / 100,
    4: float(os.getenv("PARTIAL_TP4_PERCENT", "0")) / 100,
}

# Konfigurasi Posisi Macet
STUCK_TRADE_ENABLED = os.getenv("STUCK_TRADE_ENABLED", "False").lower() in ('true', '1', 't')
STUCK_TRADE_DURATION_HOURS = int(os.getenv("STUCK_TRADE_DURATION_HOURS", 6))

# --- Konfigurasi Prioritas Risiko ---
PRIORITIZE_NORMAL_RISK = os.getenv("PRIORITIZE_NORMAL_RISK", "False").lower() in ('true', '1', 't')

# --- Konfigurasi Validitas Waktu Sinyal ---
FILTER_OLD_SIGNALS_ENABLED = os.getenv("FILTER_OLD_SIGNALS_ENABLED", "True").lower() in ('true', '1', 't')
SIGNAL_VALIDITY_MINUTES = int(os.getenv("SIGNAL_VALIDITY_MINUTES", 45))

# --- Konfigurasi Filter Tren Makro (BTC) ---
BTC_TREND_FILTER_ENABLED = os.getenv("BTC_TREND_FILTER_ENABLED", "True").lower() in ('true', '1', 't')
BTC_FILTER_TIMEFRAME = os.getenv("BTC_FILTER_TIMEFRAME", "4h")
BTC_FILTER_SMA_PERIOD = int(os.getenv("BTC_FILTER_SMA_PERIOD", 50))

# --- Konfigurasi Filter Tren Altcoin (Lokal) ---
ALTCOIN_TREND_FILTER_ENABLED = os.getenv("ALTCOIN_TREND_FILTER_ENABLED", "True").lower() in ('true', '1', 't')

# --- Konfigurasi Filter Pembelian Setelah Stop Loss ---
AVOID_BUYING_AFTER_SL = os.getenv("AVOID_BUYING_AFTER_SL", "True").lower() in ('true', '1', 't')

# --- BARU: Konfigurasi Filter Batas Maksimal Stop Loss ---
MAX_SL_PERCENTAGE_ENABLED = os.getenv("MAX_SL_PERCENTAGE_ENABLED", "True").lower() in ('true', '1', 't')
# Ambil nilai absolut dan pastikan negatif untuk perbandingan
MAX_SL_PERCENTAGE = -abs(float(os.getenv("MAX_SL_PERCENTAGE", "5.0")))