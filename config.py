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

# Konfigurasi MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = "trading_bot_db"

# --- BARU: Konfigurasi Manajemen Risiko & Posisi ---
# Konfigurasi untuk risiko 'Normal'
NORMAL_RISK_CONFIG = {
    "enabled": True,
    "max_positions": int(os.getenv("NORMAL_MAX_POSITIONS", 2)),
    "usdt_amount_per_trade": float(os.getenv("NORMAL_USDT_AMOUNT", 35.0)),
    "sl_level": int(os.getenv("NORMAL_SL_LEVEL", 1)), # 0 untuk entry, 1 untuk SL1, 2 untuk SL2
    "tp_level": int(os.getenv("NORMAL_TP_LEVEL", 4)), # Target TP utama untuk OCO
    "partial_tp": { # TP Parsial (total harus 100%)
        1: float(os.getenv("NORMAL_TP1_SELL_PERCENTAGE", 10.0)),  # Jual 10% di TP1
        2: float(os.getenv("NORMAL_TP2_SELL_PERCENTAGE", 20.0)),  # Jual 20% di TP2
        3: float(os.getenv("NORMAL_TP3_SELL_PERCENTAGE", 30.0)),  # Jual 30% di TP3
        4: float(os.getenv("NORMAL_TP4_SELL_PERCENTAGE", 40.0))   # Jual 40% di TP4
    }
}

# Konfigurasi untuk risiko 'High'
HIGH_RISK_CONFIG = {
    "enabled": True,
    "max_positions": int(os.getenv("HIGH_MAX_POSITIONS", 1)),
    "usdt_amount_per_trade": float(os.getenv("HIGH_USDT_AMOUNT", 10.0)),
    "sl_level": int(os.getenv("HIGH_SL_LEVEL", 0)), # 0 untuk entry, 1 untuk SL1, 2 untuk SL2
    "tp_level": int(os.getenv("HIGH_TP_LEVEL", 2)), # Target TP utama untuk OCO
    "partial_tp": { # TP Parsial (total harus 100%)
        1: float(os.getenv("HIGH_TP1_SELL_PERCENTAGE", 50.0)), # Jual 50% di TP1
        2: float(os.getenv("HIGH_TP2_SELL_PERCENTAGE", 50.0)), # Jual 50% di TP2
        3: float(os.getenv("HIGH_TP3_SELL_PERCENTAGE", 0.0)),
        4: float(os.getenv("HIGH_TP4_SELL_PERCENTAGE", 0.0))
    }
}

# --- Konfigurasi Trailing Stop Loss Dinamis ---
TRAILING_ENABLED = os.getenv("TRAILING_ENABLED", "True").lower() in ('true', '1', 't')
TRAILING_CONFIG = {
    "1": 0,
    "2": 1,
    "3": 2,
    "4": 3,
}

# Konfigurasi Posisi Macet
STUCK_TRADE_ENABLED = os.getenv("STUCK_TRADE_ENABLED", "False").lower() in ('true', '1', 't')
STUCK_TRADE_DURATION_HOURS = int(os.getenv("STUCK_TRADE_DURATION_HOURS", 6))
STUCK_TRADE_HOURS_THRESHOLD = int(os.getenv("STUCK_TRADE_DURATION_HOURS", 6))

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

# --- Konfigurasi Filter Batas Maksimal Stop Loss ---
MAX_SL_PERCENTAGE_ENABLED = os.getenv("MAX_SL_PERCENTAGE_ENABLED", "True").lower() in ('true', '1', 't')
# Ambil nilai absolut dan pastikan negatif untuk perbandingan
MAX_SL_PERCENTAGE = -abs(float(os.getenv("MAX_SL_PERCENTAGE", "5.0")))

# --- Konfigurasi Stop Loss Level 0 ---
SL0_PERCENTAGE = float(os.getenv("SL0_PERCENTAGE", "0.995"))