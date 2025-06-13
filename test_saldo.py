import os
import logging
from dotenv import load_dotenv

# --- Konfigurasi Awal ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- Import Komponen Bot ---
# Kita import kelas yang benar dari file-file Anda
from binance.client import BinanceClient
from binance.account import AccountManager

# Kita tidak perlu import dari config.py untuk tes spesifik ini

def test_get_balance():
    """
    Fungsi ini secara khusus menguji fungsionalitas pengambilan saldo akun.
    """
    logging.info("Memulai tes pengambilan saldo...")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        logging.error("FATAL: Kunci API tidak ditemukan di file .env")
        return

    logging.info("API Key ditemukan. Menghubungkan ke Binance...")

    try:
        binance_client = BinanceClient(api_key, api_secret)
        account_handler = AccountManager(binance_client)

        logging.info("\n--- MEMANGGIL get_account_summary() ---")
        summary = account_handler.get_account_summary()

        if not summary or 'held_assets' not in summary:
            logging.error("Gagal mendapatkan summary akun atau format tidak sesuai.")
            return
        
        # Ekstrak saldo USDT dari hasil panggilan
        # Langsung mencari aset dengan nama 'USDT'
        usdt_asset = next((asset for asset in summary.get('held_assets', []) if asset['asset'] == 'USDT'), None)
        
        logging.info(f"Total Nilai Akun (Estimasi USDT): ${summary.get('total_balance_usdt'):.2f}")

        if usdt_asset:
            logging.info("\n--- DETAIL ASET USDT ---")
            logging.info(f"  -> Total Saldo: {usdt_asset.get('total_balance'):.8f}")
            logging.info(f"  -> Saldo Tersedia (Free): {usdt_asset.get('free_balance'):.8f}")
            logging.info(f"  -> Saldo Terkunci (Locked): {usdt_asset.get('locked_balance'):.8f}")
            logging.info("------------------------------------")
            logging.info("CATATAN: Bot hanya bisa menggunakan saldo 'Tersedia (Free)' untuk trading.")
        else:
            logging.warning("\nAset USDT tidak ditemukan di dalam daftar aset Anda (atau nilainya 0).")

    except Exception as e:
        logging.error(f"Terjadi error saat menjalankan tes: {e}", exc_info=True)

if __name__ == "__main__":
    test_get_balance()