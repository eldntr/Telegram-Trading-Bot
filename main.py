# main.py
import argparse
import asyncio
import os
import config
from core.services import SignalService, TradingService, AccountService
from telegram.client import TelegramClientWrapper
from telegram.parser import TelegramMessageParser
from binance.client import BinanceClient
from binance.strategy import TradingStrategy
from binance.trader import Trader
from binance.account import AccountManager
from db.mongo_client import MongoManager
from telegram.utils import JsonWriter

async def main():
    """Fungsi utama untuk mengontrol alur kerja bot melalui argumen baris perintah."""
    # --- Inisialisasi Dependensi Utama ---
    os.makedirs("data", exist_ok=True)

    # Klien & Manager
    binance_client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    mongo_manager = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    telegram_client_wrapper = TelegramClientWrapper(config.SESSION_NAME, config.API_ID, config.API_HASH, config.PHONE_NUMBER)

    # Komponen Bisnis
    account_manager = AccountManager(binance_client)
    trader = Trader(binance_client, config.USDT_AMOUNT_PER_TRADE)
    strategy = TradingStrategy(binance_client)
    parser = TelegramMessageParser()

    # Service Layer
    signal_service = SignalService(telegram_client_wrapper, parser, mongo_manager)
    trading_service = TradingService(strategy, trader, account_manager, mongo_manager, binance_client)
    account_service = AccountService(account_manager)

    # --- Pengaturan Argumen CLI ---
    parser = argparse.ArgumentParser(
        description="Auto Trade Bot for Telegram Signals.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        'action',
        choices=['fetch', 'decide', 'execute', 'status', 'manage', 'run-all', 'autoloop'],
        help="""Pilih aksi yang ingin dijalankan:
'fetch'    : Mengambil pesan baru dari Telegram dan menyimpannya.
'decide'   : Membuat keputusan trading dari sinyal di DB.
'execute'  : Mengeksekusi keputusan 'BUY' yang disetujui.
'status'   : Memeriksa status akun Binance.
'manage'   : Menjalankan rutinitas manajemen posisi (trailing SL & stuck).
'run-all'  : Menjalankan 'fetch' > 'decide' > 'execute' satu kali.
'autoloop' : Menjalankan bot secara otomatis dalam siklus berulang.
"""
    )
    parser.add_argument('-l', '--limit', type=int, default=50, help="Jumlah pesan yang di-fetch per siklus (default: 50).")
    parser.add_argument('--initial-limit', type=int, default=100, help="Jumlah pesan yang di-fetch pada siklus pertama kali (default: 100).")
    parser.add_argument('-d', '--duration', type=int, default=0, help="Durasi (menit) untuk mode 'autoloop'. Set 0 untuk berjalan selamanya (default: selamanya).")
    parser.add_argument('--delay', type=int, default=300, help="Jeda waktu (detik) antar siklus di mode 'autoloop' (default: 300).")

    args = parser.parse_args()

    # --- Eksekusi Aksi ---
    try:
        if args.action == 'fetch':
            await signal_service.fetch_and_save_signals(message_limit=args.limit)

        elif args.action == 'decide':
            trading_service.decide_from_new_signals()

        elif args.action == 'execute':
            trading_service.execute_approved_trades()

        elif args.action == 'status':
            account_service.check_and_save_status()

        elif args.action == 'manage':
            await trading_service.manage_open_positions()

        elif args.action == 'run-all':
            print("=== Memulai Alur Kerja Lengkap (run-all) ===")
            await signal_service.fetch_and_save_signals(message_limit=args.limit)
            decisions = trading_service.decide_from_new_signals()
            trading_service.execute_approved_trades(decisions_data=decisions)
            print("\n=== Alur Kerja Lengkap Selesai ===")

        elif args.action == 'autoloop':
            await run_autoloop_routine(
                signal_service=signal_service,
                trading_service=trading_service,
                duration_minutes=args.duration,
                cycle_delay_seconds=args.delay,
                message_limit=args.limit,
                initial_fetch_limit=args.initial_limit
            )
    finally:
        mongo_manager.close_connection()
        if telegram_client_wrapper.client.is_connected():
            await telegram_client_wrapper.disconnect()


async def run_autoloop_routine(signal_service, trading_service, duration_minutes, cycle_delay_seconds, message_limit, initial_fetch_limit):
    """Menjalankan siklus bot secara terus-menerus."""
    import time
    
    end_time = None
    if duration_minutes > 0:
        print(f"--- Memulai Mode Autoloop selama {duration_minutes} menit ---")
        end_time = time.time() + duration_minutes * 60
    else:
        print("--- Memulai Mode Autoloop (Berjalan Selamanya, tekan CTRL+C untuk berhenti) ---")

    print(f"(Fetch awal: {initial_fetch_limit} pesan, per siklus: {message_limit} pesan, jeda: {cycle_delay_seconds} detik)")

    cycle_count = 0
    while True:
        if end_time and time.time() >= end_time:
            break

        cycle_count += 1
        sisa_waktu_str = f"~{int((end_time - time.time()) / 60)} menit" if end_time else "selamanya"
        print(f"\n{'='*15} Memulai Siklus #{cycle_count} (Sisa waktu: {sisa_waktu_str}) {'='*15}")

        try:
            current_fetch_limit = initial_fetch_limit if cycle_count == 1 else message_limit
            
            # 1. Fetch
            print("\n--- [1] Memulai Rutinitas Fetch Telegram ---")
            await signal_service.fetch_and_save_signals(limit=current_fetch_limit)

            # 2. Decide
            print("\n--- [2] Memulai Rutinitas Keputusan Trading ---")
            decisions = trading_service.decide_from_new_signals()
            
            # 3. Execute
            print("\n--- [3] Memulai Rutinitas Eksekusi Trading ---")
            trading_service.execute_approved_trades(decisions_data=decisions)

            # 4. Manage
            print("\n--- [4] Memulai Rutinitas Manajemen Posisi ---")
            await trading_service.manage_open_positions()

        except Exception as e:
            print(f"Terjadi error pada siklus ini: {e}. Melanjutkan ke siklus berikutnya.")

        if end_time and time.time() >= end_time:
            break

        print(f"\nSiklus selesai. Menunggu {cycle_delay_seconds} detik sebelum siklus berikutnya...")
        try:
            await asyncio.sleep(cycle_delay_seconds)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nCTRL+C terdeteksi. Menghentikan autoloop...")
            break

    print("\n--- Mode Autoloop Dihentikan ---")


if __name__ == "__main__":
    asyncio.run(main())