# main.py
import asyncio
import config
from telegram.client import TelegramClientWrapper
from telegram.parser import TelegramMessageParser
from telegram.utils import JsonWriter

async def main():
    """Fungsi utama untuk menjalankan keseluruhan proses."""
    if not all([config.API_ID, config.API_HASH, config.PHONE_NUMBER, config.TARGET_CHAT_ID]):
        print("Harap konfigurasikan variabel di file .env Anda.")
        return

    client_wrapper = TelegramClientWrapper(
        session_name=config.SESSION_NAME,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        phone_number=config.PHONE_NUMBER
    )
    
    parser = TelegramMessageParser()
    writers = {
        "all_messages": JsonWriter("parsed_messages.json"),
        "new_signals": JsonWriter("new_signals.json"),
        "market_alerts": JsonWriter("market_alerts.json"),
        "signal_updates": JsonWriter("signal_updates.json")
    }
    
    try:
        await client_wrapper.connect()
        me = await client_wrapper.client.get_me()
        print(f"Terhubung sebagai: {me.first_name}")
        
        print(f"Mengambil 50 pesan terakhir dari chat ID: {config.TARGET_CHAT_ID}...")
        messages = await client_wrapper.fetch_historical_messages(config.TARGET_CHAT_ID, limit=50)
        print(f"Berhasil mengambil {len(messages)} pesan.")
        
        if not messages: return

        parsed_data = [parser.parse_message(msg).to_dict() for msg in messages]
        print(f"Berhasil mem-parsing {len(parsed_data)} pesan.")
        
        writers["all_messages"].write(parsed_data)
        
        print("\n--- Memulai Proses Pemfilteran ---")
        filters = {
            "new_signals": "NewSignal",
            "market_alerts": "MarketAlert",
            "signal_updates": "SignalUpdate",
        }
        for key, msg_type in filters.items():
            filtered_list = [msg for msg in parsed_data if msg.get("message_type") == msg_type]
            print(f"Ditemukan {len(filtered_list)} pesan '{msg_type}'.")
            if filtered_list:
                writers[key].write(filtered_list)
            
    except Exception as e:
        print(f"\nTerjadi kesalahan: {e}")
    finally:
        if client_wrapper.client.is_connected():
            await client_wrapper.disconnect()
            print("\nKoneksi Telegram ditutup.")

if __name__ == "__main__":
    asyncio.run(main())