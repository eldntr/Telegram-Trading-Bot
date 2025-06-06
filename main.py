# Auto Trade Bot/main.py
import argparse
import asyncio
import os
from core.routines import (
    run_fetch_routine,
    run_decide_routine,
    run_execute_routine,
    run_status_routine
)

async def main():
    """Fungsi utama untuk mengontrol alur kerja bot melalui argumen baris perintah."""
    parser = argparse.ArgumentParser(
        description="Auto Trade Bot for Telegram Signals.",
        formatter_class=argparse.RawTextHelpFormatter # Untuk format help yang lebih baik
    )
    parser.add_argument(
        'action',
        choices=['fetch', 'decide', 'execute', 'status', 'run-all'],
        help="""Pilih aksi yang ingin dijalankan:
'fetch'   : Mengambil pesan baru dari Telegram dan menyimpannya ke data/.
'decide'  : Membuat keputusan trading dari data/new_signals.json.
'execute' : Mengeksekusi keputusan 'BUY' dari data/trade_decisions.json.
'status'  : Memeriksa status akun Binance dan transaksi berjalan.
'run-all' : Menjalankan 'fetch', 'decide', dan 'execute' secara berurutan di dalam memori.
"""
    )
    args = parser.parse_args()
    
    # Membuat direktori data jika belum ada
    os.makedirs("data", exist_ok=True)

    if args.action == 'fetch':
        await run_fetch_routine()
    elif args.action == 'decide':
        run_decide_routine()
    elif args.action == 'execute':
        run_execute_routine()
    elif args.action == 'status':
        run_status_routine()
    elif args.action == 'run-all':
        print("=== Memulai Alur Kerja Lengkap (run-all) ===")
        
        # 1. Fetch, dapatkan data di memori
        parsed_data = await run_fetch_routine()
        if not parsed_data:
            print("\nAlur kerja dihentikan: Tidak ada data dari Telegram.")
            return
            
        # 2. Decide, oper data dari fetch, dapatkan keputusan di memori
        decisions = run_decide_routine(parsed_data=parsed_data)
        if not decisions:
            print("\nAlur kerja dihentikan: Tidak ada keputusan yang dihasilkan.")
            return

        # 3. Execute, oper data keputusan
        run_execute_routine(decisions_data=decisions)
        
        print("\n=== Alur Kerja Lengkap Selesai ===")

if __name__ == "__main__":
    asyncio.run(main())