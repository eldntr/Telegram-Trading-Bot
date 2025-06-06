# config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER")
TARGET_CHAT_ID = int(os.getenv("TELEGRAM_TARGET_CHAT_ID", 0))
SESSION_NAME = "trading_bot_session"