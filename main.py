# Auto Trade Bot/main.py
import argparse
import asyncio
from core.routines import (
    run_fetch_routine,
    run_decide_routine,
    run_execute_routine,
    run_status_routine
)

async def main():
    """Fungsi utama untuk mengontrol alur kerja bot melalui argumen baris perintah."""
    parser = argparse.ArgumentParser(description="Auto Trade Bot for Telegram Signals.")
    parser.add_argument(
        'action',
        choices=['fetch', 'decide', 'execute', 'status', 'run-all'],
        help="""
        Pilih aksi yang ingin dijalankan:
        'fetch': Mengambil pesan baru dari Telegram.
        'decide': Membuat keputusan trading dari sinyal yang ada.
        'execute': Mengeksekusi keputusan trading 'BUY'.
        'status': Memeriksa status akun Binance.
        'run-all': Menjalankan 'fetch', 'decide', dan 'execute' secara berurutan.
        """
    )
    args = parser.parse_args()

    if args.action == 'fetch':
        await run_fetch_routine()
    elif args.action == 'decide':
        run_decide_routine()
    elif args.action == 'execute':
        run_execute_routine()
    elif args.action == 'status':
        run_status_routine()
    elif args.action == 'run-all':
        await run_fetch_routine()
        run_decide_routine()
        run_execute_routine()

if __name__ == "__main__":
    asyncio.run(main())