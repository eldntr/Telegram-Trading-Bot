# main.py

import argparse
import asyncio
import os
import time

import config
from binance.account import AccountManager
from binance.client import BinanceClient
from binance.strategy import TradingStrategy
from binance.trader import Trader
from core.services import AccountService, SignalService, TradingService
from db.mongo_client import MongoManager
from telegram.client import TelegramClientWrapper
from telegram.parser import TelegramMessageParser

# --- FUNGSI PEMBANTU UNTUK MENGELOLA SIKLUS ---

async def run_fetch_routine(signal_service: SignalService, limit: int):
    """
    Rutinitas terisolasi untuk mengambil sinyal, mengelola koneksi di dalamnya secara aman.
    """
    try:
        print("\n--- [1] Memulai Rutinitas Fetch Telegram ---")
        # Menyambungkan koneksi jaringan sebelum digunakan
        await signal_service.client_wrapper.connect()
        # Menjalankan proses fetch
        await signal_service.fetch_and_save_signals(limit=limit)
    except Exception as e:
        print(f"❌ Terjadi error dalam rutinitas fetch sinyal: {e}")
    finally:
        # Memastikan koneksi jaringan SELALU ditutup setelah selesai
        if signal_service.client_wrapper.is_connected():
            await signal_service.client_wrapper.disconnect()
            print("Koneksi jaringan Telegram ditutup dengan aman.")
            await asyncio.sleep(1) # Jeda singkat untuk memberi waktu OS melepaskan lock file

async def run_trading_cycle(trading_service: TradingService, account_service: AccountService):
    """Menjalankan semua langkah trading setelah fetch."""
    try:
        print("\n--- [2] Memulai Rutinitas Keputusan Trading ---")
        decisions = trading_service.decide_from_new_signals()
        
        print("\n--- [3] Memulai Rutinitas Eksekusi Trading ---")
        trading_service.execute_approved_trades(decisions_data=decisions)

        print("\n--- [4] Memulai Rutinitas Manajemen Posisi ---")
        await trading_service.manage_open_positions()

        print("\n--- [5] Memulai Rutinitas Cek Status Akun ---")
        account_service.check_and_save_status()
    except Exception as e:
        print(f"❌ Terjadi error dalam siklus trading: {e}")

async def run_autoloop_mode(services: dict, args: argparse.Namespace):
    """Menjalankan bot dalam mode loop otomatis."""
    end_time = None
    if args.duration > 0:
        print(f"--- Memulai Mode Autoloop selama {args.duration} menit ---")
        end_time = time.time() + args.duration * 60
    else:
        print("--- Memulai Mode Autoloop (Berjalan Selamanya, tekan CTRL+C untuk berhenti) ---")

    # --- PERBAIKAN DI SINI ---
    # Menggunakan nama argumen yang benar: args.initial_limit
    print(f"(Fetch awal: {args.initial_limit} pesan, per siklus: {args.limit} pesan, jeda: {args.delay} detik)")

    cycle_count = 0
    while True:
        if end_time and time.time() >= end_time: break

        cycle_count += 1
        sisa_waktu_str = f"~{int((end_time - time.time()) / 60)} menit" if end_time else "selamanya"
        print(f"\n{'='*15} Memulai Siklus #{cycle_count} (Sisa waktu: {sisa_waktu_str}) {'='*15}")
        
        # --- PERBAIKAN DI SINI ---
        # Menggunakan nama argumen yang benar: args.initial_limit
        current_fetch_limit = args.initial_limit if cycle_count == 1 else args.limit
        
        await run_fetch_routine(services['signal'], current_fetch_limit)
        await run_trading_cycle(services['trading'], services['account'])
        
        print(f"\nSiklus selesai. Menunggu {args.delay} detik sebelum siklus berikutnya...")
        try:
            await asyncio.sleep(args.delay)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nCTRL+C terdeteksi. Menghentikan autoloop...")
            break
    print("\n--- Mode Autoloop Dihentikan ---")

# --- FUNGSI UTAMA ---

async def main():
    """Fungsi utama untuk menginisialisasi dan menjalankan bot."""
    os.makedirs("data", exist_ok=True)
    
    # --- 1. Memuat Semua Konfigurasi di Satu Tempat ---
    user_config = config.load_user_config()
    binance_creds = user_config.get("binance_credentials", {})
    
    # Inisialisasi klien dan manajer.
    mongo_manager = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    print("Berhasil terhubung ke MongoDB.")

    telegram_client = TelegramClientWrapper(config.SESSION_NAME, config.API_ID, config.API_HASH, config.PHONE_NUMBER)
    binance_client = BinanceClient(binance_creds.get("api_key"), binance_creds.get("api_secret"))
    
    # ---2. Inject Konfigurasi ke dalam Service & Strategy ---
    parser = TelegramMessageParser()
    account_manager = AccountManager(binance_client)
    trader = Trader(binance_client, user_config)
    strategy = TradingStrategy(binance_client, user_config.get("strategy_filters", {}))

    # Kumpulkan semua service dalam satu dictionary untuk kemudahan akses
    services = {
        'signal': SignalService(telegram_client, parser, mongo_manager, config.TARGET_CHAT_ID),
        'trading': TradingService(
            strategy=strategy,
            trader=trader,
            account_manager=account_manager,
            mongo=mongo_manager,
            binance_client=binance_client,
            user_config=user_config
        ),
        'account': AccountService(account_manager, user_config)
    }

    # Konfigurasi CLI yang sama seperti yang Anda gunakan sebelumnya
    cli_parser = argparse.ArgumentParser(
        description="Auto Trade Bot for Telegram Signals.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    cli_parser.add_argument('action', choices=['fetch', 'decide', 'execute', 'status', 'manage', 'run-all', 'autoloop'])
    cli_parser.add_argument('-l', '--limit', type=int, default=50)
    cli_parser.add_argument('--initial-limit', type=int, default=100) # Defined as --initial-limit
    cli_parser.add_argument('-d', '--duration', type=int, default=0)
    cli_parser.add_argument('--delay', type=int, default=300)
    args = cli_parser.parse_args()

    # Eksekusi aksi berdasarkan pilihan CLI
    try:
        if args.action == 'fetch': await run_fetch_routine(services['signal'], args.limit)
        elif args.action == 'decide': services['trading'].decide_from_new_signals()
        elif args.action == 'execute': services['trading'].execute_approved_trades()
        elif args.action == 'status': services['account'].check_and_save_status()
        elif args.action == 'manage': await services['trading'].manage_open_positions()
        elif args.action == 'run-all':
            await run_fetch_routine(services['signal'], args.limit)
            await run_trading_cycle(services['trading'], services['account'])
        elif args.action == 'autoloop':
            await run_autoloop_mode(services, args)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nBot dihentikan oleh pengguna.")
    finally:
        # Tutup koneksi DB hanya sekali di akhir program
        if mongo_manager and mongo_manager.client:
            mongo_manager.close_connection()
            print("Koneksi MongoDB ditutup.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Terjadi error tak terduga di level utama: {e}")