# Auto Trade Bot/core/routines.py
import sys
import time
import json
import os
import asyncio
import config

from telegram.client import TelegramClientWrapper
from telegram.parser import TelegramMessageParser
from telegram.utils import JsonWriter
from binance.client import BinanceClient
from binance.strategy import TradingStrategy
from binance.account import AccountManager
from binance.trader import Trader

def _load_json_file(file_name: str, directory: str = "data"):
    """Fungsi helper untuk memuat data dari file JSON di dalam direktori data."""
    file_path = os.path.join(directory, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

async def run_fetch_routine():
    """Mengambil pesan, mem-parsing, dan MENGEMBALIKAN data yang sudah diparsing."""
    print("--- [1] Memulai Rutinitas Fetch Telegram ---")
    client_wrapper = TelegramClientWrapper(config.SESSION_NAME, config.API_ID, config.API_HASH, config.PHONE_NUMBER)
    parser = TelegramMessageParser()
    parsed_data = []
    try:
        await client_wrapper.connect()
        messages = await client_wrapper.fetch_historical_messages(config.TARGET_CHAT_ID, limit=50)
        if not messages: return []
        
        parsed_data = [parser.parse_message(msg).to_dict() for msg in messages]
        
        JsonWriter("parsed_messages.json").write(parsed_data)
        JsonWriter("new_signals.json").write([m for m in parsed_data if m.get("message_type") == "NewSignal"])
        JsonWriter("market_alerts.json").write([m for m in parsed_data if m.get("message_type") == "MarketAlert"])
        JsonWriter("signal_updates.json").write([m for m in parsed_data if m.get("message_type") == "SignalUpdate"])
        print("--- Rutinitas Fetch Telegram Selesai ---")
    finally:
        if client_wrapper.client.is_connected(): await client_wrapper.disconnect()
    return parsed_data

def run_decide_routine(parsed_data=None):
    """Menerima data, membuat keputusan, dan MENGEMBALIKAN keputusan tersebut."""
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
    """Menerima data keputusan dan mengeksekusinya."""
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
        print("Tidak ada keputusan 'BUY' untuk dieksekusi.")
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
    """Memeriksa status akun dan order aktif."""
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