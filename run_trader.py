# Auto Trade Bot/run_trader.py
import json
from typing import List, Dict, Any

from binance.client import BinanceClient
from binance.strategy import TradingStrategy
from telegram.utils import JsonWriter # Menggunakan kembali JsonWriter yang sudah ada

def load_signals(file_path: str) -> List[Dict[str, Any]]:
    """Memuat sinyal dari file JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            signals = json.load(f)
            # Memastikan data adalah list
            return signals if isinstance(signals, list) else []
    except FileNotFoundError:
        print(f"Error: File sinyal tidak ditemukan di {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Error: Gagal mem-parsing JSON dari {file_path}")
        return []

def main():
    """
    Fungsi utama untuk menjalankan proses evaluasi sinyal.
    """
    # 1. Inisialisasi Klien, Strategi, dan Penulis JSON
    binance_client = BinanceClient()
    strategy = TradingStrategy(binance_client)
    decision_writer = JsonWriter("trade_decisions.json")

    # 2. Muat Sinyal Baru dari file
    print("Memuat sinyal dari 'new_signals.json'...")
    new_signals = load_signals("new_signals.json")

    if not new_signals:
        print("Tidak ada sinyal baru untuk dievaluasi. Keluar.")
        return

    # 3. Evaluasi setiap sinyal
    print(f"\nMengevaluasi {len(new_signals)} sinyal...")
    all_decisions = []
    for signal in new_signals:
        coin_pair = signal.get('coin_pair', 'N/A')
        print(f"--- Mengevaluasi Sinyal untuk: {coin_pair} ---")
        
        trade_decision = strategy.evaluate_new_signal(signal)
        decision_dict = trade_decision.to_dict()
        all_decisions.append(decision_dict)
        
        # Cetak keputusan individual dalam format JSON
        print(json.dumps(decision_dict, indent=4))
        print("--------------------------------------------------\n")

    # 4. Simpan semua keputusan ke satu file
    decision_writer.write(all_decisions)

if __name__ == "__main__":
    main()