import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER") 
TARGET_CHAT_ID = int(os.getenv("TELEGRAM_TARGET_CHAT_ID")) 

SESSION_NAME = "trading_bot_session"
    
if __name__ == "__main__":
    print("API_ID:", API_ID)
    print("API_HASH:", API_HASH)
    print("PHONE_NUMBER:", PHONE_NUMBER)
    print("TARGET_CHAT_ID:", TARGET_CHAT_ID)
    print("SESSION_NAME:", SESSION_NAME)