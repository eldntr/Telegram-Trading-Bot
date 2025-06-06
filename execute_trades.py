# Auto Trade Bot/execute_trades.py
import json
import sys
import time
import config
from binance.client import BinanceClient
from binance.account import AccountManager
from binance.trader import Trader
from telegram.utils import JsonWriter

def load_json_file(file_path: str):
    """Memuat data dari file JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def main():
    print("--- Memulai Eksekusi Trade ---")
    
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("\nERROR: Kunci API Binance belum diatur di .env")
        sys.exit(1)
        
    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    account_manager = AccountManager(client)
    trader = Trader(client, config.USDT_AMOUNT_PER_TRADE)
    log_writer = JsonWriter("trade_log.json")

    print("\n[Langkah 1/3] Memeriksa status akun awal...")
    account_summary = account_manager.get_account_summary()
    if not account_summary:
        print("Gagal mendapatkan status akun. Proses dihentikan.")
        return
    print(f"Status Akun Awal: Saldo USDT tersedia ${next((a['free_balance'] for a in account_summary.get('held_assets', []) if a['asset'] == 'USDT'), 0):.2f}")

    print("\n[Langkah 2/3] Memuat keputusan trading...")
    trade_decisions = load_json_file("trade_decisions.json")
    if not trade_decisions:
        print("File trade_decisions.json tidak ditemukan atau kosong. Tidak ada yang dieksekusi.")
        return
        
    buy_decisions = [d for d in trade_decisions if d.get('decision') == 'BUY']
    if not buy_decisions:
        print("Tidak ada sinyal dengan keputusan 'BUY'. Proses selesai.")
        return
    print(f"Ditemukan {len(buy_decisions)} sinyal 'BUY'.")

    print("\n[Langkah 3/3] Mengeksekusi trade satu per satu...")
    trade_logs = []
    for decision in buy_decisions:
        coin_pair = decision.get("coin_pair", "N/A")
        print(f"\n--- Mengevaluasi: {coin_pair} ---")
        
        # Selalu gunakan data 'account_summary' yang paling baru untuk setiap trade
        result = trader.execute_trade(decision, account_summary)
        
        status = result.get('status', 'UNKNOWN')
        reason = result.get('reason', 'No reason provided.')
        print(f"Hasil: {status} - {reason}")
        
        log_entry = {
            "coin_pair": coin_pair,
            "decision_details": decision,
            "execution_result": result
        }
        trade_logs.append(log_entry)
        
        # --- LOGIKA BARU UNTUK MENCEGAH DOUBLE BUY ---
        # Jika trade berhasil, perbarui (refresh) data status akun
        if status == 'SUCCESS':
            print("Memperbarui status akun setelah trade berhasil...")
            time.sleep(1) # Beri jeda singkat untuk sinkronisasi server
            refreshed_summary = account_manager.get_account_summary()
            if refreshed_summary:
                account_summary = refreshed_summary # Ganti data lama dengan data baru
                print("Status akun berhasil diperbarui.")
            else:
                print("PERINGATAN: Gagal memperbarui status akun. Pengecekan untuk trade selanjutnya mungkin tidak akurat.")
        # --- AKHIR LOGIKA BARU ---
        
    if trade_logs:
        log_writer.write(trade_logs)
        print("\n--- Semua proses selesai. Log eksekusi disimpan di trade_log.json ---")

if __name__ == "__main__":
    main()