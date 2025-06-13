# Auto Trade Bot/core/routines.py

import sys
import time
import json
import os
import asyncio
import config
from datetime import datetime, timezone

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
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("Kunci API Binance tidak dikonfigurasi. Melewatkan eksekusi.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    manager = AccountManager(client)
    trader = Trader(client, config.USDT_AMOUNT_PER_TRADE)
    mongo = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    
    decisions = _load_json_file("trade_decisions.json")
    if not decisions:
        print("Tidak ada file keputusan trading untuk diproses.")
        mongo.close_connection()
        return

    buy_decisions = [d for d in decisions if d.get('decision') == 'BUY']
    if not buy_decisions:
        print("Tidak ditemukan keputusan 'BUY'. Tidak ada yang dieksekusi.")
        mongo.close_connection()
        return
    
    trade_logs = []
    for decision in buy_decisions:
        account_summary = manager.get_account_summary() # Selalu ambil summary terbaru
        if not account_summary: 
            print("Gagal mengambil summary akun, eksekusi dihentikan.")
            break
        
        result = trader.execute_trade(decision, account_summary)
        trade_logs.append({"decision_details": decision, "execution_result": result})
        
        # --- BARU: Simpan data trade ke DB untuk manajemen posisi ---
        if result.get('status') == 'SUCCESS':
            buy_order = result.get('buy_order', {})
            oco_order = result.get('oco_order', {})
            
            if buy_order and oco_order:
                coin_pair = buy_order.get('symbol')
                avg_price = float(buy_order.get('cummulativeQuoteQty', 0)) / float(buy_order.get('executedQty', 1))
                actual_balance = float(buy_order.get('executedQty', 0))

                position_doc = {
                    "coin_pair": coin_pair,
                    "buy_price": avg_price,
                    "quantity": actual_balance,
                    "order_list_id": oco_order.get('orderListId'),
                    "signal_data": decision,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                mongo.save_open_position(position_doc)
            
            time.sleep(2) # Beri jeda setelah trade sukses
                    
    if trade_logs: JsonWriter("trade_log.json").write(trade_logs)
    mongo.close_connection()
    print("\n--- Rutinitas Eksekusi Trading Selesai ---")

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

async def run_manage_positions_routine():
    """
    Memeriksa semua posisi yang dilacak, menerapkan strategi trailing SL dinamis
    dan menangani posisi yang macet.
    """
    print("\n--- [4] Memulai Rutinitas Manajemen Posisi (Trailing & Macet) ---")
    if not all([config.BINANCE_API_KEY, config.BINANCE_API_SECRET]):
        print("Manajemen posisi dilewati: Kunci API tidak ditemukan.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    mongo = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)

    # 1. Ambil semua posisi yang seharusnya aktif dari database kita
    db_positions = mongo.get_all_open_positions()
    if not db_positions:
        print("Tidak ada posisi aktif yang dilacak di database untuk dikelola.")
        mongo.close_connection()
        return

    # 2. Ambil semua order yang aktif di Binance untuk sinkronisasi
    active_binance_orders = client.get_open_orders()
    active_symbols_on_binance = {o['symbol'] for o in active_binance_orders} if active_binance_orders else set()

    # 3. Proses setiap posisi yang dilacak
    print(f"Memeriksa {len(db_positions)} posisi yang dilacak di DB...")
    for position in db_positions:
        symbol = position['coin_pair']
        
        # 3.1. Sinkronisasi: Hapus dari DB jika sudah tidak aktif di Binance
        if symbol not in active_symbols_on_binance:
            print(f"  - Posisi {symbol} sudah tertutup di Binance. Menghapus dari pelacakan DB.")
            mongo.delete_open_position(symbol)
            continue

        print(f"\n- Memeriksa posisi aktif: {symbol}...")
        try:
            # Dapatkan data penting dari dokumen posisi DB
            buy_price = position['buy_price']
            quantity = position['quantity']
            order_list_id = position['order_list_id']
            signal_targets = position.get('signal_data', {}).get('targets', [])

            # Dapatkan harga pasar saat ini
            current_price = client.get_current_price(symbol)
            if not current_price:
                print(f"  Gagal mendapatkan harga untuk {symbol}. Melewatkan.")
                continue

            # Dapatkan order SL aktif dari daftar order Binance
            all_orders_for_symbol = [o for o in active_binance_orders if o.get('symbol') == symbol]
            sl_order = next((o for o in all_orders_for_symbol if o['type'] == 'STOP_LOSS_LIMIT'), None)
            if not sl_order:
                print(f"  Peringatan: Tidak ditemukan order SL untuk {symbol}. Akan disinkronkan pada siklus berikutnya.")
                continue
            current_sl_price = float(sl_order['stopPrice'])
            
            print(f"  Info: Harga Beli: ${buy_price:.4f}, Harga Saat Ini: ${current_price:.4f}, SL Saat Ini: ${current_sl_price:.4f}")

            # 3.2. Pengecekan Posisi Macet (Stuck Trade)
            if config.STUCK_TRADE_ENABLED:
                pos_timestamp_str = position.get('timestamp')
                order_datetime = datetime.fromisoformat(pos_timestamp_str)
                now_utc = datetime.now(timezone.utc)
                elapsed_hours = (now_utc - order_datetime).total_seconds() / 3600
                print(f"  Info: Usia posisi: {elapsed_hours:.2f} jam.")

                if elapsed_hours >= config.STUCK_TRADE_DURATION_HOURS:
                    tp1_price = next((t['price'] for t in signal_targets if t.get('level') == 1), None)
                    if tp1_price and current_price < tp1_price:
                        print(f"  >> TINDAKAN [MACET]: Posisi {symbol} dianggap macet (> {config.STUCK_TRADE_DURATION_HOURS} jam & di bawah TP1). Menutup posisi...")
                        if client.cancel_oco_order(symbol, order_list_id):
                            await asyncio.sleep(2)
                            if client.place_market_sell_order(symbol, float(quantity)):
                                print(f"  >> SUKSES: Posisi macet {symbol} berhasil ditutup.")
                                mongo.delete_open_position(symbol)
                            else:
                                print(f"  >> SANGAT KRITIS: Gagal menjual {symbol} setelah OCO dibatalkan!")
                        else:
                            print(f"  >> KRITIS: Gagal membatalkan OCO untuk posisi macet {symbol}.")
                        continue

            # 3.3. Pengecekan Trailing Stop Loss
            if config.TRAILING_ENABLED:
                sl_target_levels = {0: {'price': buy_price}} # TP0 adalah harga beli
                for t in signal_targets: sl_target_levels[t['level']] = {'price': t['price']}
                
                new_sl_price_candidate = 0
                for trigger_level_str, new_sl_level in config.TRAILING_CONFIG.items():
                    trigger_level = int(trigger_level_str)
                    if trigger_level not in sl_target_levels: continue
                    
                    trigger_price = sl_target_levels[trigger_level]['price']
                    if current_price >= trigger_price and new_sl_level in sl_target_levels:
                        potential_sl = sl_target_levels[new_sl_level]['price']
                        if potential_sl > new_sl_price_candidate:
                            print(f"  Kondisi trailing terpenuhi: Harga lewati TP{trigger_level} (${trigger_price:.4f}). Kandidat SL baru: TP{new_sl_level} (${potential_sl:.4f})")
                            new_sl_price_candidate = potential_sl

                if new_sl_price_candidate > current_sl_price:
                    print(f"  >> TINDAKAN [TRAILING]: Memindahkan SL untuk {symbol} dari ${current_sl_price:.4f} ke ${new_sl_price_candidate:.4f}")
                    final_tp_price = max(t['price'] for t in signal_targets) if signal_targets else buy_price * 1.5
                    
                    if client.cancel_oco_order(symbol, order_list_id):
                        await asyncio.sleep(2)
                        new_oco = client.place_oco_sell_order(symbol, quantity, final_tp_price, new_sl_price_candidate)
                        if new_oco:
                            print(f"  >> SUKSES: Trailing SL untuk {symbol} berhasil diterapkan.")
                            position['order_list_id'] = new_oco.get('orderListId')
                            mongo.save_open_position(position)
                        else:
                             print(f"  >> SANGAT KRITIS: Aset {symbol} tidak terproteksi setelah gagal menempatkan OCO baru!")
                    else:
                        print(f"  >> KRITIS: Gagal membatalkan OCO lama untuk trailing.")
                else:
                    print("  Info: Tidak ada kondisi trailing yang memicu pembaruan SL.")

        except Exception as e:
            print(f"  LOG ERROR: Terjadi kesalahan tak terduga saat memproses {symbol}. Error: {e}. Melanjutkan...")
            continue
        
    mongo.close_connection()
    print("\n--- Rutinitas Manajemen Posisi Selesai ---")

async def run_autoloop_routine(duration_minutes: int, message_limit: int, cycle_delay_seconds: int, initial_fetch_limit: int):
    end_time = None
    if duration_minutes > 0:
        print(f"--- Memulai Mode Autoloop selama {duration_minutes} menit ---")
        end_time = time.time() + duration_minutes * 60
    else:
        print("--- Memulai Mode Autoloop (Berjalan Selamanya, tekan CTRL+C untuk berhenti) ---")
    
    print(f"(Fetch awal: {initial_fetch_limit} pesan, per siklus: {message_limit} pesan, jeda: {cycle_delay_seconds} detik)")

    cycle_count = 0
    while True:
        if end_time and time.time() >= end_time:
            break

        cycle_count += 1
        sisa_waktu_str = f"~{int((end_time - time.time()) / 60)} menit" if end_time else "selamanya"
        print(f"\n{'='*15} Memulai Siklus #{cycle_count} (Sisa waktu: {sisa_waktu_str}) {'='*15}")
        
        try:
            current_fetch_limit = initial_fetch_limit if cycle_count == 1 else message_limit
            
            parsed_data = await run_fetch_routine(message_limit=current_fetch_limit)
            decisions = run_decide_routine(parsed_data=parsed_data)
            run_execute_routine(decisions_data=decisions)
            
            await run_manage_positions_routine()

        except Exception as e:
            print(f"Terjadi error pada siklus ini: {e}. Melanjutkan ke siklus berikutnya.")
        
        if end_time and time.time() >= end_time:
            break
        
        print(f"\nSiklus selesai. Menunggu {cycle_delay_seconds} detik sebelum siklus berikutnya...")
        try:
            await asyncio.sleep(cycle_delay_seconds)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nCTRL+C terdeteksi. Menghentikan autoloop...")
            break
    
    print("\n--- Mode Autoloop Dihentikan ---")

if __name__ == "__main__":
    # This part is in main.py, so it's not needed here.
    # But for context, this is how the main loop would be called.
    pass