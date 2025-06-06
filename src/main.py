import asyncio
from . import config
from .telegram_client import TelegramClientWrapper
from .signal_parser import TelegramSignalParser
from .json_writer import JsonWriter

async def main():
    """
    Fungsi utama untuk menjalankan proses pengambilan pesan, 
    parsing, pemfilteran, dan penyimpanan.
    """
    if not all([config.API_ID, config.API_HASH, config.PHONE_NUMBER, config.TARGET_CHAT_ID]):
        print("Harap konfigurasikan API_ID, API_HASH, PHONE_NUMBER, dan TARGET_CHAT_ID di file .env Anda.")
        return

    client_wrapper = TelegramClientWrapper(
        session_name=config.SESSION_NAME,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        phone_number=config.PHONE_NUMBER
    )
    
    parser = TelegramSignalParser()
    # Siapkan writer untuk setiap file output JSON
    all_messages_writer = JsonWriter("parsed_messages.json")
    new_signals_writer = JsonWriter("new_signals.json")
    market_alerts_writer = JsonWriter("market_alerts.json")
    signal_updates_writer = JsonWriter("signal_updates.json") # DITAMBAHKAN
    
    try:
        await client_wrapper.connect()
        me = await client_wrapper.client.get_me()
        print(f"Terhubung sebagai: {me.first_name}")
        
        print(f"Mengambil 50 pesan terakhir dari chat ID: {config.TARGET_CHAT_ID}...")
        historical_messages = await client_wrapper.fetch_historical_messages(
            chat_id=config.TARGET_CHAT_ID,
            limit=50
        )
        print(f"Berhasil mengambil {len(historical_messages)} pesan.")
        
        if not historical_messages:
            print("Tidak ada pesan yang ditemukan.")
            return

        # 1. Parse semua pesan yang telah diambil
        parsed_data = [parser.parse_message(msg).to_dict() for msg in historical_messages]
        print(f"Berhasil mem-parsing {len(parsed_data)} pesan.")
        
        # Simpan semua hasil parse untuk pengecekan umum
        if parsed_data:
            all_messages_writer.write(parsed_data)
        
        # 2. Filter data yang sudah di-parsing berdasarkan message_type
        print("\n--- Memulai Proses Pemfilteran ---")
        new_signals = [msg for msg in parsed_data if msg.get("message_type") == "NewSignal"]
        market_alerts = [msg for msg in parsed_data if msg.get("message_type") == "MarketAlert"]
        signal_updates = [msg for msg in parsed_data if msg.get("message_type") == "SignalUpdate"] # DITAMBAHKAN
        
        print(f"Ditemukan {len(new_signals)} pesan 'NewSignal'.")
        print(f"Ditemukan {len(market_alerts)} pesan 'MarketAlert'.")
        print(f"Ditemukan {len(signal_updates)} pesan 'SignalUpdate'.") # DITAMBAHKAN
        
        # 3. Simpan hasil filter ke file JSON masing-masing
        if new_signals:
            new_signals_writer.write(new_signals)
        else:
            print("Tidak ada pesan 'NewSignal' untuk disimpan.")
            
        if market_alerts:
            market_alerts_writer.write(market_alerts)
        else:
            print("Tidak ada pesan 'MarketAlert' untuk disimpan.")

        if signal_updates:
            signal_updates_writer.write(signal_updates)
        else:
            print("Tidak ada pesan 'SignalUpdate' untuk disimpan.")
            
    except Exception as e:
        print(f"\nTerjadi kesalahan: {e}")
    finally:
        if client_wrapper.client.is_connected():
            await client_wrapper.disconnect()
            print("\nKoneksi Telegram ditutup.")

if __name__ == "__main__":
    asyncio.run(main())