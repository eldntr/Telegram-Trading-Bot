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
from db.mongo_client import MongoManager

def _load_json_file(file_name: str, directory: str = "data"):
    file_path = os.path.join(directory, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

async def run_fetch_routine(message_limit: int = 50):
    print(f"\n--- [1] Memulai Rutinitas Fetch Telegram (Limit: {message_limit} pesan) ---")
    client_wrapper = TelegramClientWrapper(config.SESSION_NAME, config.API_ID, config.API_HASH, config.PHONE_NUMBER)
    parser = TelegramMessageParser()
    mongo_manager = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    parsed_data = []

    try:
        await client_wrapper.connect()
        messages = await client_wrapper.fetch_historical_messages(config.TARGET_CHAT_ID, limit=message_limit)
        if not messages: 
            print("Tidak ada pesan baru yang diambil.")
            return []
        
        parsed_data = [parser.parse_message(msg).to_dict() for msg in messages]
        JsonWriter("parsed_messages.json").write(parsed_data)
        
        new_signals = [m for m in parsed_data if m.get("message_type") == "NewSignal"]
        JsonWriter("new_signals.json").write(new_signals)
        
        if new_signals:
            mongo_manager.save_new_signals(new_signals)

        print("--- Rutinitas Fetch Telegram Selesai ---")
    finally:
        if client_wrapper.client.is_connected(): await client_wrapper.disconnect()
        mongo_manager.close_connection()
        
    return parsed_data

def run_decide_routine(parsed_data=None):
    print("\n--- [2] Memulai Rutinitas Keputusan Trading ---")
    client = BinanceClient()
    strategy = TradingStrategy(client)
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

    decisions = _load_json_file("trade_decisions.json")
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
    print("\n--- Memulai Rutinitas Pengecekan Status ---")
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

# --- BARU: Rutinitas untuk Trailing Stop Loss ---
async def run_manage_positions_routine():
    """Memeriksa semua posisi OCO yang terbuka dan menerapkan strategi trailing stop loss."""
    print("\n--- [4] Memulai Rutinitas Manajemen Posisi (Trailing SL) ---")
    
    if not config.TRAILING_ENABLED:
        print("Fitur trailing dinonaktifkan di konfigurasi.")
        return
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("API Key/Secret Binance tidak ditemukan.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    mongo = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    
    open_orders = client.get_open_orders()
    if not open_orders:
        print("Tidak ada order terbuka yang ditemukan untuk dikelola.")
        return

    # Filter hanya order OCO. Kita bisa identifikasi dari order yang punya 'orderListId' > -1
    # dan kita hanya butuh satu entri per 'orderListId'
    oco_orders = {}
    for order in open_orders:
        if order.get('orderListId', -1) != -1:
            oco_orders[order['orderListId']] = order
    
    if not oco_orders:
        print("Tidak ada order OCO aktif yang ditemukan.")
        return
        
    print(f"Ditemukan {len(oco_orders)} OCO order aktif. Memeriksa untuk trailing...")

    for order_list_id, order in oco_orders.items():
        symbol = order['symbol']
        print(f"\n- Memeriksa {symbol} (OrderListId: {order_list_id})")

        # 1. Ambil data sinyal asli dari DB
        signal_data = mongo.get_signal_by_pair(symbol)
        if not signal_data:
            print(f"  Peringatan: Tidak ditemukan data sinyal untuk {symbol} di DB. Melewatkan.")
            continue
            
        # 2. Ambil harga pasar saat ini
        current_price = client.get_current_price(symbol)
        if current_price is None:
            print(f"  Gagal mendapatkan harga terkini untuk {symbol}. Melewatkan.")
            continue

        # 3. Cari stop loss saat ini dari salah satu order di list OCO
        sl_order = next((o for o in open_orders if o['orderListId'] == order_list_id and o['type'] == 'STOP_LOSS_LIMIT'), None)
        if not sl_order:
            print(f"  Tidak dapat menemukan order STOP_LOSS_LIMIT untuk {symbol}. Melewatkan.")
            continue
        
        current_sl_price = float(sl_order['stopPrice'])
        quantity = sl_order['origQty']
        
        print(f"  Harga Saat Ini: ${current_price:.4f}, SL Saat Ini: ${current_sl_price:.4f}")

        # 4. Terapkan logika trailing
        new_sl_price = 0
        try:
            # Iterasi target dari sinyal, mulai dari level yang dikonfigurasi
            for target in signal_data.get('targets', []):
                if target['level'] < config.MIN_TRAILING_TP_LEVEL:
                    continue
                
                tp_price = target['price']
                trigger_price = tp_price * (1 + config.TRAILING_TRIGGER_PERCENTAGE)
                
                # Cek jika harga saat ini melebihi trigger DAN TP ini lebih tinggi dari SL saat ini
                if current_price >= trigger_price and tp_price > current_sl_price:
                    print(f"  Kondisi trailing TERPENUHI pada TP{target['level']} (Harga: ${tp_price:.4f})")
                    new_sl_price = max(new_sl_price, tp_price) # Selalu ambil yang tertinggi
        except Exception as e:
            print(f"  Error saat memproses target untuk {symbol}: {e}")
            continue

        # 5. Eksekusi pemindahan SL jika ada target baru
        if new_sl_price > current_sl_price:
            print(f"  >> TINDAKAN: Memindahkan SL untuk {symbol} dari ${current_sl_price:.4f} ke ${new_sl_price:.4f}")
            
            # Ambil TP akhir (TP4) dari sinyal
            final_tp_price = signal_data['targets'][-1]['price']

            # A. Batalkan OCO lama
            cancel_result = client.cancel_oco_order(symbol, order_list_id)
            if not cancel_result:
                print(f"  >> KRITIS: Gagal membatalkan OCO lama untuk {symbol}. Intervensi manual mungkin diperlukan.")
                continue
            
            print(f"  Sukses membatalkan OCO lama. Menunggu 2 detik...")
            await asyncio.sleep(2)

            # B. Pasang OCO baru
            print(f"  Menempatkan OCO baru: TP=${final_tp_price:.4f}, SL=${new_sl_price:.4f}")
            new_oco_result = client.place_oco_sell_order(
                symbol=symbol,
                quantity=quantity,
                take_profit_price=final_tp_price,
                stop_loss_price=new_sl_price
            )

            if not new_oco_result:
                print(f"  >> SANGAT KRITIS: Aset {symbol} tidak terproteksi! Gagal menempatkan OCO baru setelah membatalkan yang lama.")
                # Di sini bisa ditambahkan notifikasi darurat (misal: ke Telegram)
            else:
                print(f"  >> SUKSES: Trailing SL untuk {symbol} berhasil diterapkan.")
        else:
            print(f"  Tidak ada tindakan trailing yang diperlukan untuk {symbol}.")

    mongo.close_connection()
    print("\n--- Rutinitas Manajemen Posisi Selesai ---")


async def run_autoloop_routine(duration_minutes: int, message_limit: int, cycle_delay_seconds: int):
    """Menjalankan siklus fetch-decide-execute-manage secara berulang."""
    end_time = None
    if duration_minutes > 0:
        print(f"--- Memulai Mode Autoloop selama {duration_minutes} menit ---")
        end_time = time.time() + duration_minutes * 60
    else:
        print("--- Memulai Mode Autoloop (Berjalan Selamanya, tekan CTRL+C untuk berhenti) ---")
    
    print(f"(Setiap siklus akan mengambil {message_limit} pesan, dengan jeda {cycle_delay_seconds} detik)")

    cycle_count = 0
    while True:
        if end_time and time.time() >= end_time:
            break

        cycle_count += 1
        sisa_waktu_str = f"~{int((end_time - time.time()) / 60)} menit" if end_time else "selamanya"
        print(f"\n{'='*15} Memulai Siklus #{cycle_count} (Sisa waktu: {sisa_waktu_str}) {'='*15}")
        
        try:
            # 1. Fetch
            parsed_data = await run_fetch_routine(message_limit=message_limit)
            # 2. Decide
            decisions = run_decide_routine(parsed_data=parsed_data)
            # 3. Execute
            run_execute_routine(decisions_data=decisions)
            # 4. Manage (Trailing SL) - PERUBAHAN DI SINI
            if config.TRAILING_ENABLED:
                await run_manage_positions_routine()

        except Exception as e:
            print(f"Terjadi error pada siklus ini: {e}. Melanjutkan ke siklus berikutnya.")
        
        if end_time and time.time() >= end_time:
            break
        
        print(f"\nSiklus selesai. Menunggu {cycle_delay_seconds} detik sebelum siklus berikutnya...")
        try:
            time.sleep(cycle_delay_seconds)
        except KeyboardInterrupt:
            print("\nCTRL+C terdeteksi. Menghentikan autoloop...")
            break
    
    print("\n--- Mode Autoloop Dihentikan ---")