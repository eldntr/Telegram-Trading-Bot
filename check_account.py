# Auto Trade Bot/check_account.py
import sys
import config
from binance.client import BinanceClient
from binance.account import AccountManager
from telegram.utils import JsonWriter # Menggunakan kembali JsonWriter yang sudah ada

def main():
    """
    Fungsi utama untuk memeriksa status akun Binance dan menyimpannya ke file JSON.
    """
    print("--- Memulai Pengecekan Akun Binance ---")
    
    # 1. Periksa Konfigurasi Kunci API
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("\nERROR: Harap atur BINANCE_API_KEY dan BINANCE_API_SECRET di file .env Anda.")
        sys.exit(1)

    # 2. Inisialisasi Klien, Manajer Akun, dan Penulis JSON
    client = BinanceClient(
        api_key=config.BINANCE_API_KEY, 
        api_secret=config.BINANCE_API_SECRET
    )
    manager = AccountManager(client)
    writer = JsonWriter("account_status.json")

    # 3. Dapatkan Ringkasan Akun
    summary = manager.get_account_summary()

    # 4. Simpan hasil ke file JSON
    if summary:
        print("\n--- Ringkasan Akun Berhasil Didapatkan ---")
        writer.write(summary)
        print(f"Total Estimasi Nilai Akun: ${summary.get('total_balance_usdt', 0)}")
        print(f"Jumlah Aset yang Dipegang: {len(summary.get('held_assets', []))}")
        print("\nDetail lengkap telah disimpan ke file 'account_status.json'.")
    else:
        print("\n--- Gagal Mendapatkan Ringkasan Akun ---")
        writer.write({"error": "Gagal mendapatkan ringkasan akun. Periksa log di atas untuk detail."})

if __name__ == "__main__":
    main()