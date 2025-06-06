# Auto Trade Bot/core/routines.py
import sys
import time
import json
import os
import asyncio
import config

# (Salin semua fungsi import dan fungsi-fungsi rutin lainnya dari respons sebelumnya)
# ...
from telegram.client import TelegramClientWrapper
from telegram.parser import TelegramMessageParser
from telegram.utils import JsonWriter
from binance.client import BinanceClient
from binance.strategy import TradingStrategy
from binance.account import AccountManager
from binance.trader import Trader

def _load_json_file(file_name: str, directory: str = "data"):
    file_path = os.path.join(directory, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

async def run_fetch_routine(message_limit: int = 50):
    print(f"--- [1] Memulai Rutinitas Fetch Telegram (Limit: {message_limit} pesan) ---")
    client_wrapper = TelegramClientWrapper(config.SESSION_NAME, config.API_ID, config.API_HASH, config.PHONE_NUMBER)
    parser = TelegramMessageParser()
    parsed_data = []
    try:
        await client_wrapper.connect()
        messages = await client_wrapper.fetch_historical_messages(config.TARGET_CHAT_ID, limit=message_limit)
        if not messages: 
            print("Tidak ada pesan baru yang diambil.")
            return []
        
        parsed_data = [parser.parse_message(msg).to_dict() for msg in messages]
        JsonWriter("parsed_messages.json").write(parsed_data)
        JsonWriter("new_signals.json").write([m for m in parsed_data if m.get("message_type") == "NewSignal"])
        print("--- Rutinitas Fetch Telegram Selesai ---")
    finally:
        if client_wrapper.client.is_connected(): await client_wrapper.disconnect()
    return parsed_data

def run_decide_routine(parsed_data=None):
    print("\n--- [2] Memulai Rutinitas Keputusan Trading ---")
    client = BinanceClient()
    strategy = TradingStrategy(client)
    if parsed_data:
        new_signals = [msg for msg in parsed_data if msg.get("message_type") == "NewSignal"]
    else:
        new_signals = _load_json_file("new_signals.json")
    if not new_signals:
        print("Tidak ada sinyal baru untuk dievaluasi.")
        return []
    all_decisions = [strategy.evaluate_new_signal(signal).to_dict() for signal in new_signals]
    JsonWriter("trade_decisions.json").write(all_decisions)
    print(f"Berhasil membuat {len(all_decisions)} keputusan trading.")
    print("--- Rutinitas Keputusan Trading Selesai ---")
    return all_decisions

def run_execute_routine(decisions_data=None):
    print("\n--- [3] Memulai Rutinitas Eksekusi Trading ---")
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET: return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    manager = AccountManager(client)
    trader = Trader(client, config.USDT_AMOUNT_PER_TRADE)
    account_summary = manager.get_account_summary()
    if not account_summary: return

    decisions = decisions_data if decisions_data is not None else _load_json_file("trade_decisions.json")
    if not decisions: return

    buy_decisions = [d for d in decisions if d.get('decision') == 'BUY']
    if not buy_decisions:
        print("Tidak ditemukan keputusan 'BUY'. Tidak ada yang dieksekusi.")
        return
    
    print(f"Ditemukan {len(buy_decisions)} keputusan 'BUY' untuk dieksekusi.")
    trade_logs = []
    for decision in buy_decisions:
        result = trader.execute_trade(decision, account_summary)
        trade_logs.append({"decision_details": decision, "execution_result": result})
        if result.get('status') == 'SUCCESS':
            time.sleep(1)
            refreshed_summary = manager.get_account_summary()
            if refreshed_summary: account_summary = refreshed_summary
    if trade_logs: JsonWriter("trade_log.json").write(trade_logs)
    print("--- Rutinitas Eksekusi Trading Selesai ---")

def run_status_routine():
    print("--- Memulai Rutinitas Pengecekan Status ---")
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET: return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    print("\n[1/2] Memeriksa Saldo Aset...")
    manager = AccountManager(client)
    summary = manager.get_account_summary()
    if summary: 
        JsonWriter("account_status.json").write(summary)
        print(f"Total Estimasi Nilai Akun: ${summary.get('total_balance_usdt', 0)}")
    
    print("\n[2/2] Memeriksa Transaksi Berjalan (Open Orders)...")
    open_orders = client.get_open_orders()
    if not open_orders:
        print("Tidak ada transaksi berjalan (order aktif) yang ditemukan.")
    else:
        processed = [{"symbol": o.get('symbol'), "type": o.get('type'), "side": o.get('side'), "quantity": o.get('origQty'), "price": o.get('price'), "stopPrice": o.get('stopPrice')} for o in open_orders]
        JsonWriter("open_orders_status.json").write(processed)
        for order in processed:
            if order['type'] == 'LIMIT_MAKER': print(f"  - TAKE PROFIT | {order['symbol']:<12} | Target: {order['price']}")
            elif order['type'] == 'STOP_LOSS_LIMIT': print(f"  - STOP LOSS   | {order['symbol']:<12} | Pemicu: {order['stopPrice']}")
    print("\n--- Rutinitas Pengecekan Status Selesai ---")

async def run_autoloop_routine(duration_minutes: int, message_limit: int, cycle_delay_seconds: int):
    """Menjalankan siklus fetch-decide-execute secara berulang."""
    end_time = None
    if duration_minutes > 0:
        print(f"--- Memulai Mode Autoloop selama {duration_minutes} menit ---")
        end_time = time.time() + duration_minutes * 60
    else:
        print("--- Memulai Mode Autoloop (Berjalan Selamanya, tekan CTRL+C untuk berhenti) ---")
    
    print(f"(Setiap siklus akan mengambil {message_limit} pesan, dengan jeda {cycle_delay_seconds} detik)")

    cycle_count = 0
    while True:
        # Jika durasi ditentukan, cek apakah sudah waktunya berhenti
        if end_time and time.time() >= end_time:
            break

        cycle_count += 1
        sisa_waktu_str = f"~{int((end_time - time.time()) / 60)} menit" if end_time else "selamanya"
        print(f"\n{'='*15} Memulai Siklus #{cycle_count} (Sisa waktu: {sisa_waktu_str}) {'='*15}")
        
        try:
            parsed_data = await run_fetch_routine(message_limit=message_limit)
            if parsed_data:
                decisions = run_decide_routine(parsed_data=parsed_data)
                if decisions:
                    run_execute_routine(decisions_data=decisions)
        except Exception as e:
            print(f"Terjadi error pada siklus ini: {e}. Melanjutkan ke siklus berikutnya.")
        
        # Cek lagi setelah siklus selesai, untuk kasus jika siklus berjalan lama
        if end_time and time.time() >= end_time:
            break
        
        print(f"\nSiklus selesai. Menunggu {cycle_delay_seconds} detik sebelum siklus berikutnya...")
        try:
            time.sleep(cycle_delay_seconds)
        except KeyboardInterrupt:
            print("\nCTRL+C terdeteksi. Menghentikan autoloop...")
            break
    
    print("\n--- Mode Autoloop Dihentikan ---")