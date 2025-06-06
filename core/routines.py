# Auto Trade Bot/core/routines.py
import sys
import time
import json
import asyncio
import config

# Import dari modul telegram
from telegram.client import TelegramClientWrapper
from telegram.parser import TelegramMessageParser
from telegram.utils import JsonWriter

# Import dari modul binance
from binance.client import BinanceClient
from binance.strategy import TradingStrategy
from binance.account import AccountManager
from binance.trader import Trader

# --- Rutinitas 1: Mengambil & Mem-parsing Pesan Telegram ---
async def run_fetch_routine():
    """Mengambil pesan dari Telegram, mem-parsing, dan menyimpannya ke file JSON."""
    print("--- [1] Memulai Rutinitas Fetch Telegram ---")
    client_wrapper = TelegramClientWrapper(
        session_name=config.SESSION_NAME,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        phone_number=config.PHONE_NUMBER
    )
    parser = TelegramMessageParser()
    
    try:
        await client_wrapper.connect()
        print(f"Mengambil 50 pesan terakhir dari chat ID: {config.TARGET_CHAT_ID}...")
        messages = await client_wrapper.fetch_historical_messages(config.TARGET_CHAT_ID, limit=50)
        
        if not messages:
            print("Tidak ada pesan yang diambil. Selesai.")
            return

        print(f"Berhasil mengambil {len(messages)} pesan. Memulai parsing...")
        parsed_data = [parser.parse_message(msg).to_dict() for msg in messages]
        
        writers = {
            "all_messages": JsonWriter("parsed_messages.json"),
            "new_signals": JsonWriter("new_signals.json"),
            "market_alerts": JsonWriter("market_alerts.json"),
            "signal_updates": JsonWriter("signal_updates.json")
        }
        filters = {"new_signals": "NewSignal", "market_alerts": "MarketAlert", "signal_updates": "SignalUpdate"}

        writers["all_messages"].write(parsed_data)
        for key, msg_type in filters.items():
            filtered_list = [msg for msg in parsed_data if msg.get("message_type") == msg_type]
            if filtered_list:
                writers[key].write(filtered_list)
        
        print("--- Rutinitas Fetch Telegram Selesai ---")

    except Exception as e:
        print(f"Terjadi kesalahan pada rutinitas fetch: {e}")
    finally:
        if client_wrapper.client.is_connected():
            await client_wrapper.disconnect()

# --- Rutinitas 2: Membuat Keputusan Trading ---
def run_decide_routine():
    """Membaca sinyal baru dan menghasilkan file keputusan trading."""
    print("\n--- [2] Memulai Rutinitas Keputusan Trading ---")
    client = BinanceClient()
    strategy = TradingStrategy(client)
    decision_writer = JsonWriter("trade_decisions.json")

    try:
        with open("new_signals.json", 'r', encoding='utf-8') as f:
            new_signals = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("File new_signals.json tidak ditemukan atau kosong. Lewati rutinitas.")
        return

    if not new_signals:
        print("Tidak ada sinyal baru untuk dievaluasi.")
        return

    all_decisions = [strategy.evaluate_new_signal(signal).to_dict() for signal in new_signals]
    decision_writer.write(all_decisions)
    print(f"Berhasil membuat {len(all_decisions)} keputusan trading di trade_decisions.json.")
    print("--- Rutinitas Keputusan Trading Selesai ---")

# --- Rutinitas 3: Mengeksekusi Trading ---
def run_execute_routine():
    """Membaca keputusan 'BUY' dan mengeksekusinya."""
    print("\n--- [3] Memulai Rutinitas Eksekusi Trading ---")
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("Kunci API Binance tidak diatur. Lewati rutinitas.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    manager = AccountManager(client)
    trader = Trader(client, config.USDT_AMOUNT_PER_TRADE)
    log_writer = JsonWriter("trade_log.json")
    
    account_summary = manager.get_account_summary()
    if not account_summary:
        print("Gagal mendapatkan status akun. Eksekusi dibatalkan.")
        return

    try:
        with open("trade_decisions.json", 'r', encoding='utf-8') as f:
            decisions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("File trade_decisions.json tidak ditemukan atau kosong. Lewati rutinitas.")
        return
        
    buy_decisions = [d for d in decisions if d.get('decision') == 'BUY']
    if not buy_decisions:
        print("Tidak ditemukan keputusan 'BUY'. Tidak ada yang dieksekusi.")
        return
    
    print(f"Ditemukan {len(buy_decisions)} keputusan 'BUY' untuk dieksekusi.")
    trade_logs = []
    for decision in buy_decisions:
        coin_pair = decision.get("coin_pair", "N/A")
        print(f"\n--- Mengevaluasi: {coin_pair} ---")
        result = trader.execute_trade(decision, account_summary)
        trade_logs.append({"decision_details": decision, "execution_result": result})
        
        if result.get('status') == 'SUCCESS':
            print("Trade berhasil, memperbarui status akun untuk iterasi selanjutnya...")
            time.sleep(1)
            refreshed_summary = manager.get_account_summary()
            if refreshed_summary:
                account_summary = refreshed_summary
            else:
                print("PERINGATAN: Gagal memperbarui status akun.")

    if trade_logs:
        log_writer.write(trade_logs)
    print("--- Rutinitas Eksekusi Trading Selesai ---")

# --- Rutinitas Tambahan: Cek Status Akun & Transaksi Berjalan ---
def run_status_routine():
    """
    Memeriksa dan menampilkan status akun Binance, termasuk saldo dan order aktif (transaksi berjalan).
    """
    print("--- Memulai Rutinitas Pengecekan Status ---")
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("Kunci API Binance tidak diatur. Lewati rutinitas.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    
    # Bagian 1: Cek Saldo Aset
    print("\n[1/2] Memeriksa Saldo Aset...")
    manager = AccountManager(client)
    summary = manager.get_account_summary()
    if summary:
        JsonWriter("account_status.json").write(summary)
        print(f"Total Estimasi Nilai Akun: ${summary.get('total_balance_usdt', 0)}")
        print("Detail saldo disimpan di account_status.json.")
    else:
        print("Gagal mendapatkan ringkasan saldo akun.")

    # Bagian 2: Cek Order Aktif (Transaksi Berjalan)
    print("\n[2/2] Memeriksa Transaksi Berjalan (Open Orders)...")
    open_orders = client.get_open_orders()
    
    if open_orders is None:
        print("Gagal mengambil data order aktif.")
    elif not open_orders:
        print("Tidak ada transaksi berjalan (order aktif) yang ditemukan.")
    else:
        print(f"Ditemukan {len(open_orders)} order aktif:")
        processed_orders = []
        for order in open_orders:
            # Karena OCO terdiri dari 2 order (STOP_LOSS_LIMIT dan LIMIT_MAKER), kita bisa kelompokkan
            info = {
                "symbol": order.get('symbol'),
                "orderId": order.get('orderId'),
                "type": order.get('type'),
                "side": order.get('side'),
                "quantity": order.get('origQty'),
                "price": order.get('price'),
                "stopPrice": order.get('stopPrice'),
                "orderListId": order.get('orderListId') # ID untuk grup OCO
            }
            processed_orders.append(info)
        
        # Cetak ke konsol
        for order in processed_orders:
            if order['type'] == 'LIMIT_MAKER':
                print(f"  - TAKE PROFIT  | {order['symbol']:<12} | Qty: {order['quantity']:<15} | Target Harga: {order['price']}")
            elif order['type'] == 'STOP_LOSS_LIMIT':
                print(f"  - STOP LOSS    | {order['symbol']:<12} | Qty: {order['quantity']:<15} | Pemicu Harga: {order['stopPrice']}")

        # Simpan ke file
        JsonWriter("open_orders_status.json").write(processed_orders)
        print("\nDetail transaksi berjalan disimpan di open_orders_status.json.")

    print("\n--- Rutinitas Pengecekan Status Selesai ---")