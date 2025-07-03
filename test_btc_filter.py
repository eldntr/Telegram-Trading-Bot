# Nama file: test_btc_filter.py

import os
import numpy as np
from dotenv import load_dotenv

# Memuat komponen yang relevan dari kode Anda
from binance.client import BinanceClient
import config

def run_btc_health_check():
    """
    Fungsi mandiri untuk menjalankan dan menampilkan hasil
    dari pengecekan kondisi pasar BTC.
    """
    print("=============================================")
    print("==   Memulai Tes Filter Kondisi Pasar BTC  ==")
    print("=============================================")

    # Inisialisasi Binance Client
    try:
        # Client akan mengambil kredensial dari config secara otomatis
        client = BinanceClient()
        print("✅ Binance Client berhasil diinisialisasi.")
    except Exception as e:
        print(f"❌ Gagal menginisialisasi Binance Client: {e}")
        return

    # Menambahkan fungsi get_klines jika belum ada di client.py
    # Ini untuk memastikan tes bisa berjalan bahkan sebelum Anda memodifikasi file client.py
    if not hasattr(client, 'get_klines'):
        print("[INFO] Menambahkan fungsi `get_klines` sementara untuk pengujian.")
        def get_klines(self, symbol: str, interval: str, limit: int = 100):
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            data = self._send_request("GET", "/klines", params)
            return data if data else None
        # Monkey-patch the method to the instance
        client.get_klines = get_klines.__get__(client, BinanceClient)


    # Ambil parameter dari konfigurasi
    symbol = "BTCUSDT"
    interval = config.BTC_FILTER_TIMEFRAME
    period = config.BTC_FILTER_SMA_PERIOD

    print(f"\nParameter yang digunakan:")
    print(f"  - Simbol    : {symbol}")
    print(f"  - Timeframe : {interval}")
    print(f"  - Periode SMA: {period}")
    
    print("\nMengambil data candlestick dari Binance...")

    try:
        # 1. Ambil data klines (candlestick) dari Binance
        klines = client.get_klines(symbol=symbol, interval=interval, limit=period)

        if not klines or len(klines) < period:
            print(f"\n❌ Gagal mendapatkan data klines yang cukup.")
            print(f"  - Data yang dibutuhkan: {period}")
            print(f"  - Data yang diterima  : {len(klines) if klines else 0}")
            return

        print(f"✅ Berhasil mendapatkan {len(klines)} data candlestick.")

        # 2. Ekstrak harga penutupan (close price)
        close_prices = [float(k[4]) for k in klines]
        current_price = close_prices[-1]

        # 3. Hitung Simple Moving Average (SMA)
        sma_value = np.mean(close_prices)

        print("\n--- HASIL ANALISIS ---")
        print(f"Harga BTC Saat Ini         : ${current_price:,.2f}")
        print(f"Nilai SMA {period} ({interval})     : ${sma_value:,.2f}")
        print("------------------------")

        # 4. Buat keputusan berdasarkan perbandingan harga
        if current_price >= sma_value:
            print("✅ KESIMPULAN: PASAR SEHAT")
            print("   (Harga saat ini berada di atas atau sama dengan rata-rata pergerakannya)")
            print("\n   Rekomendasi untuk Bot: BOLEH MELAKUKAN PEMBELIAN")
        else:
            print("❌ KESIMPULAN: PASAR BERISIKO (KOREKSI)")
            print("   (Harga saat ini berada di bawah rata-rata pergerakannya)")
            print("\n   Rekomendasi untuk Bot: JANGAN MELAKUKAN PEMBELIAN BARU")
        
        print("\n=============================================")


    except Exception as e:
        print(f"\nTerjadi kesalahan fatal saat proses pengujian: {e}")


if __name__ == "__main__":
    # Pastikan library numpy sudah terinstall
    try:
        import numpy
    except ImportError:
        print("Error: Library 'numpy' tidak ditemukan. Silakan install dengan 'pip install numpy'")
        exit()
        
    run_btc_health_check()