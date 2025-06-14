# Nama file: test_advanced_filter.py (Perbaikan Final f-string)

import os
import numpy as np
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Tuple, Dict, Any

# Memuat komponen yang relevan dari kode Anda
from binance.client import BinanceClient
import config

# ==================== FUNGSI INDIKATOR (Tidak berubah) ====================
def calculate_rsi(prices, period=14):
    """Menghitung Relative Strength Index (RSI)."""
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = deltas * (deltas > 0)
    losses = -deltas * (deltas < 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ==================== FUNGSI ANALISIS BARU ====================
def analyze_asset_condition(client, symbol: str, interval: str, sma_period: int, rsi_period: int, end_time_ms: int) -> Dict[str, Any]:
    """
    Menganalisis kondisi sebuah aset (BTC atau Altcoin) pada waktu tertentu dan mengembalikan data teknikalnya.
    """
    data_limit = max(sma_period, rsi_period) + 1
    klines = client.get_klines(symbol=symbol, interval=interval, endTime=end_time_ms, limit=data_limit)

    if not klines or len(klines) < data_limit:
        return {"error": f"Data tidak cukup untuk {symbol}"}

    close_prices = [float(k[4]) for k in klines]
    current_price = close_prices[-1]
    
    sma_value = np.mean(close_prices[-sma_period:])
    rsi_value = calculate_rsi(close_prices, period=rsi_period)
    
    is_above_sma = current_price >= sma_value

    return {
        "symbol": symbol,
        "price": current_price,
        "sma": sma_value,
        "rsi": rsi_value,
        "is_above_sma": is_above_sma,
        "error": None
    }

# ==================== FUNGSI UTAMA PENGUJIAN ====================
def run_advanced_test(signal: Dict[str, Any]):
    """
    Menjalankan pengujian filter berlapis untuk sebuah sinyal trading.
    """
    print("==========================================================")
    print("== Tes Filter Berlapis (Global BTC + Lokal Altcoin)   ==")
    print("==========================================================")

    signal_timestamp_str = signal.get("timestamp")
    if not signal_timestamp_str:
        print("❌ Error: Sinyal tidak memiliki 'timestamp'.")
        return

    try:
        client = BinanceClient()
        def get_klines_with_params(self, symbol: str, interval: str, endTime: int, limit: int):
            params = {"symbol": symbol, "interval": interval, "endTime": endTime, "limit": limit}
            return self._send_request("GET", "/klines", params)
        client.get_klines = get_klines_with_params.__get__(client, BinanceClient)
        print("✅ Binance Client berhasil diinisialisasi.")
    except Exception as e:
        print(f"❌ Gagal menginisialisasi Binance Client: {e}")
        return

    try:
        target_dt_naive = datetime.strptime(signal_timestamp_str, "%Y-%m-%d %H:%M:%S")
        target_dt_utc = target_dt_naive.astimezone(timezone.utc)
        end_time_ms = int(target_dt_utc.timestamp() * 1000)
        print(f"\n menganalisis sinyal pada waktu (UTC): {target_dt_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    except ValueError:
        print(f"❌ Format 'timestamp' sinyal salah. Gunakan format 'YYYY-MM-DD HH:MM:SS'.")
        return

    interval = config.BTC_FILTER_TIMEFRAME
    sma_period = config.BTC_FILTER_SMA_PERIOD
    rsi_period = 14

    # --- LANGKAH 1: ANALISIS KONDISI PASAR GLOBAL (BTC) ---
    print("\n--- Menganalisis Kondisi Pasar Global (BTC)... ---")
    btc_condition = analyze_asset_condition(client, "BTCUSDT", interval, sma_period, rsi_period, end_time_ms)

    if btc_condition["error"]:
        print(f"❌ Gagal menganalisis BTC: {btc_condition['error']}")
        return

    # ========================= PERBAIKAN 1 DI SINI =========================
    btc_rsi_str = f"{btc_condition['rsi']:.2f}" if btc_condition['rsi'] is not None else 'N/A'
    print(f"Harga BTC: ${btc_condition['price']:,.2f} | SMA {sma_period}: ${btc_condition['sma']:,.2f} | RSI: {btc_rsi_str}")
    # =====================================================================

    market_status = ""
    if btc_condition["is_above_sma"]:
        market_status = "🟢 HIJAU (Aman)"
    else:
        market_status = "🟡 KUNING (Waspada/Netral)"
    
    print(f"Status Pasar Global: {market_status}")

    # --- LANGKAH 2: EVALUASI SINYAL BERDASARKAN STATUS PASAR ---
    altcoin_symbol = signal["symbol"]
    print(f"\n--- Mengevaluasi Sinyal Untuk {altcoin_symbol}... ---")

    if market_status == "🟢 HIJAU (Aman)":
        print("✅ KEPUTUSAN: LANJUTKAN PEMBELIAN (Posisi Normal)")
        print(f"   Alasan: Pasar global sedang aman, sinyal {altcoin_symbol} dapat dieksekusi.")

    elif market_status == "🟡 KUNING (Waspada/Netral)":
        print("   Pasar global sedang waspada. Melakukan pengecekan kedua pada koin lokal...")
        
        altcoin_condition = analyze_asset_condition(client, altcoin_symbol, interval, sma_period, rsi_period, end_time_ms)
        
        if altcoin_condition["error"]:
            print(f"❌ Gagal menganalisis {altcoin_symbol}: {altcoin_condition['error']}")
            return
        
        # ========================= PERBAIKAN 2 DI SINI =========================
        alt_rsi_str = f"{altcoin_condition['rsi']:.2f}" if altcoin_condition['rsi'] is not None else 'N/A'
        print(f"Harga {altcoin_symbol}: ${altcoin_condition['price']:,.2f} | SMA {sma_period}: ${altcoin_condition['sma']:,.2f} | RSI: {alt_rsi_str}")
        # =====================================================================

        if altcoin_condition["is_above_sma"]:
            print("\n⚡️ KEPUTUSAN: LANJUTKAN PEMBELIAN (Posisi Lebih Kecil & SL Ketat)")
            print(f"   Alasan: {altcoin_symbol} menunjukkan kekuatan sendiri (di atas SMA-nya) meskipun pasar global sedang netral.")
        else:
            print("\n❌ KEPUTUSAN: JANGAN BELI")
            print(f"   Alasan: Pasar global sedang netral DAN {altcoin_symbol} juga menunjukkan kelemahan (di bawah SMA-nya). Risiko terlalu tinggi.")
    
    print("\n==========================================================")


if __name__ == "__main__":
    # ========================= PUSAT KONTROL BACKTEST =========================
    sinyal_untuk_dites = {
        "symbol": "TURBOUSDT",
        "timestamp": "2025-06-14 10:46:00",
        # "entry": 0.4816,
        # "risk_level": "High"
    }
    # ========================================================================
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError as e:
        print(f"Error: Library '{e.name}' tidak ditemukan. Silakan install.")
        exit()
        
    run_advanced_test(signal=sinyal_untuk_dites)