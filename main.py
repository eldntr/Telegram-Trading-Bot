# Auto Trade Bot/main.py (Versi Perbaikan)
import argparse
import asyncio
import os
from core.routines import (
    run_fetch_routine,
    run_decide_routine,
    run_execute_routine,
    run_status_routine,
    run_autoloop_routine,
    run_manage_positions_routine
)

async def main():
    """Fungsi utama untuk mengontrol alur kerja bot melalui argumen baris perintah."""
    parser = argparse.ArgumentParser(
        description="Auto Trade Bot for Telegram Signals.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        'action',
        choices=['fetch', 'decide', 'execute', 'status', 'run-all', 'autoloop', 'manage'],
        help="""Pilih aksi yang ingin dijalankan:
'fetch'    : Mengambil pesan baru dari Telegram.
'decide'   : Membuat keputusan trading dari sinyal yang ada.
'execute'  : Mengeksekusi keputusan 'BUY'.
'status'   : Memeriksa status akun Binance dan transaksi berjalan.
'manage'   : Menjalankan rutinitas manajemen posisi (trailing SL) satu kali.
'run-all'  : Menjalankan 'fetch' > 'decide' > 'execute' satu kali.
'autoloop' : Menjalankan bot secara otomatis dalam siklus berulang.
"""
    )
    # Argumen Tambahan untuk Kustomisasi
    parser.add_argument('-l', '--limit', type=int, default=50, help="Jumlah pesan yang di-fetch per siklus (default: 50).")
    parser.add_argument('--initial-limit', type=int, default=100, help="Jumlah pesan yang di-fetch pada siklus pertama kali (default: 100).") # <-- BARU
    parser.add_argument('-d', '--duration', type=int, default=0, help="Durasi (menit) untuk mode 'autoloop'. Set 0 untuk berjalan selamanya (default: selamanya).")
    parser.add_argument('--delay', type=int, default=300, help="Jeda waktu (detik) antar siklus di mode 'autoloop' (default: 300).")
    
    args = parser.parse_args()
    
    os.makedirs("data", exist_ok=True)

    if args.action == 'fetch':
        await run_fetch_routine(message_limit=args.limit)
    elif args.action == 'decide':
        run_decide_routine()
    elif args.action == 'execute':
        run_execute_routine()
    elif args.action == 'status':
        run_status_routine()
    elif args.action == 'manage':
        await run_manage_positions_routine()
    elif args.action == 'run-all':
        print("=== Memulai Alur Kerja Lengkap (run-all) ===")
        parsed_data = await run_fetch_routine(message_limit=args.limit)
        decisions = run_decide_routine(parsed_data=parsed_data)
        run_execute_routine(decisions_data=decisions)
        print("\n=== Alur Kerja Lengkap Selesai ===")
    elif args.action == 'autoloop':
        await run_autoloop_routine(
            duration_minutes=args.duration,
            message_limit=args.limit,
            cycle_delay_seconds=args.delay,
            initial_fetch_limit=args.initial_limit # <-- BARU
        )

if __name__ == "__main__":
    asyncio.run(main())