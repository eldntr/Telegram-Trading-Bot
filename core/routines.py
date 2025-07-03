# Auto Trade Bot/core/routines.py (VERSI HYBRID STRATEGY)

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

# Fungsi helper yang tidak berubah
def _load_json_file(file_name: str, directory: str = "data"):
    """Membaca file JSON dari direktori data."""
    file_path = os.path.join(directory, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Mengembalikan None jika file tidak ditemukan atau error saat parsing
        return None

async def run_fetch_routine(message_limit: int = 50):
    """Mengambil pesan dari Telegram, mem-parsing, dan menyimpannya."""
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
        
        # Filter hanya sinyal baru dan simpan ke DB
        new_signals = [m for m in parsed_data if m.get("message_type") == "NewSignal"]
        if new_signals:
            mongo_manager.save_new_signals(new_signals)
            print(f"Berhasil menyimpan {len(new_signals)} sinyal baru ke database.")

    finally:
        if client_wrapper.client.is_connected(): await client_wrapper.disconnect()
        mongo_manager.close_connection()
    return parsed_data

def run_decide_routine():
    """Mengevaluasi sinyal yang belum diproses dan membuat keputusan trading."""
    print("\n--- [2] Memulai Rutinitas Keputusan Trading ---")
    mongo_manager = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    # Asumsi ada fungsi untuk mengambil sinyal yang belum diproses
    new_signals = mongo_manager.get_all_unprocessed_signals()
    mongo_manager.close_connection()
    
    if not new_signals:
        print("Tidak ada sinyal baru untuk dievaluasi.")
        return []

    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("Kunci API Binance tidak dikonfigurasi. Rutinitas keputusan dilewati.")
        return []
    
    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    strategy = TradingStrategy(client)
    all_decisions = [strategy.evaluate_new_signal(signal).to_dict() for signal in new_signals]
    
    print(f"Mengevaluasi {len(new_signals)} sinyal, menghasilkan {len(all_decisions)} keputusan.")
    JsonWriter("trade_decisions.json").write(all_decisions)
    return all_decisions

def run_execute_routine():
    """Mengeksekusi keputusan 'BUY' yang telah dibuat."""
    print("\n--- [3] Memulai Rutinitas Eksekusi Trading ---")
    if not (config.BINANCE_API_KEY and config.BINANCE_API_SECRET):
        print("Eksekusi dilewati: Kunci API Binance tidak dikonfigurasi.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    manager = AccountManager(client)
    trader = Trader(client, config.USDT_AMOUNT_PER_TRADE)
    mongo = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    
    decisions = _load_json_file("trade_decisions.json")
    if not decisions:
        print("Tidak ada file keputusan trading untuk dieksekusi.")
        return
        
    buy_decisions = [d for d in decisions if d.get('decision') == 'BUY']
    if not buy_decisions:
        print("Tidak ada keputusan 'BUY' untuk dieksekusi.")
        return
    
    print(f"Ditemukan {len(buy_decisions)} keputusan 'BUY'. Mencoba mengeksekusi...")
    for decision in buy_decisions:
        account_summary = manager.get_account_summary()
        if not account_summary:
            print("Gagal mendapatkan ringkasan akun. Eksekusi dihentikan.")
            break
        
        result = trader.execute_trade(decision, account_summary)
        
        if result.get('status') == 'SUCCESS':
            buy_order = result.get('buy_order', {})
            oco_order = result.get('oco_order', {})
            
            if buy_order and oco_order:
                qty = float(buy_order.get('executedQty', 0))
                if qty == 0: continue # Hindari pembagian dengan nol

                buy_price = float(buy_order.get('cummulativeQuoteQty', 0)) / qty
                position_doc = {
                    "coin_pair": buy_order.get('symbol'),
                    "buy_price": buy_price,
                    "initial_quantity": qty,
                    "remaining_quantity": qty,
                    "order_list_id": oco_order.get('orderListId'),
                    "signal_data": decision,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "partial_tps_taken": [] # <-- Kunci untuk melacak TP parsial
                }
                mongo.save_open_position(position_doc)
                print(f"SUKSES: Posisi {position_doc['coin_pair']} dibuka dan disimpan ke DB.")
            time.sleep(2) # Jeda antar eksekusi
    mongo.close_connection()

def run_status_routine():
    # Fungsi ini tidak memerlukan modifikasi untuk strategi hybrid
    print("\n--- Memulai Rutinitas Pengecekan Status ---")
    # Logika status routine Anda bisa diletakkan di sini
    pass

async def run_manage_positions_routine():
    """
    Mengelola posisi terbuka dengan strategi hybrid yang lebih tangguh.
    Menambahkan validasi untuk menangani format data lama.
    """
    print("\n--- [4] Memulai Rutinitas Manajemen Posisi (HYBRID STRATEGY) ---")
    if not all([config.BINANCE_API_KEY, config.BINANCE_API_SECRET]):
        print("Manajemen posisi dilewati: Kunci API tidak ditemukan.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    mongo = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    db_positions = mongo.get_all_open_positions()

    if not db_positions:
        print("Tidak ada posisi aktif di DB untuk dikelola.")
        mongo.close_connection()
        return

    active_binance_orders = client.get_open_orders()
    active_symbols_on_binance = {o['symbol'] for o in active_binance_orders} if active_binance_orders else set()
    all_tickers = client.get_all_tickers()
    if not all_tickers:
        print("Gagal mendapatkan harga ticker, manajemen posisi dibatalkan.")
        mongo.close_connection()
        return

    print(f"Memeriksa {len(db_positions)} posisi yang dilacak di DB...")
    for position in db_positions:
        symbol = position.get('coin_pair')
        if not symbol:
            continue # Lewati jika dokumen tidak valid

        # Sinkronisasi: Jika posisi sudah tidak ada di Binance, hapus dari DB
        if symbol not in active_symbols_on_binance:
            print(f"  - INFO: Posisi {symbol} sudah tertutup di Binance. Menghapus dari pelacakan DB.")
            mongo.delete_open_position(symbol)
            continue

        print(f"\n- Mengevaluasi posisi aktif: {symbol}...")
        try:
            # === PERBAIKAN DIMULAI DI SINI ===
            # Validasi bahwa semua field yang dibutuhkan ada di dokumen posisi
            required_keys = ['initial_quantity', 'remaining_quantity', 'buy_price', 'order_list_id', 'signal_data']
            if not all(key in position for key in required_keys):
                print(f"  - WARNING: Posisi {symbol} di DB memiliki format lama (field tidak lengkap). Posisi ini akan DILEWATI.")
                print("  -          Harap tutup posisi ini secara manual di Binance dan hapus koleksi 'open_positions' di DB.")
                continue # Lanjut ke posisi berikutnya tanpa menyebabkan error
            # === AKHIR PERBAIKAN ===

            current_price = float(all_tickers.get(symbol, 0))
            if not current_price:
                print(f"  - WARNING: Tidak dapat menemukan harga terkini untuk {symbol}.")
                continue

            # Ambil data penting (sekarang aman karena sudah divalidasi)
            order_list_id = position['order_list_id']
            signal_targets = position.get('signal_data', {}).get('targets', [])
            initial_quantity = position['initial_quantity']
            remaining_quantity = position['remaining_quantity']
            partial_tps_taken = position.get('partial_tps_taken', [])
            buy_price = position['buy_price']
            
            # --- LOGIKA PARTIAL TAKE PROFIT (Tidak ada perubahan di sini) ---
            for target in sorted(signal_targets, key=lambda t: t['level']):
                tp_level = target['level']
                tp_price = target['price']
                
                if current_price >= tp_price and tp_level not in partial_tps_taken:
                    partial_tp_percent = config.PARTIAL_TP_CONFIG.get(tp_level, 0)
                    
                    if partial_tp_percent > 0:
                        print(f"  >> TINDAKAN [PARTIAL TP]: Harga lewati TP{tp_level} (${tp_price:.4f}). Menjual {partial_tp_percent*100}%...")
                        
                        if not client.cancel_oco_order(symbol, order_list_id):
                            print(f"  >> KRITIS: Gagal membatalkan OCO lama untuk {symbol}. Aksi dibatalkan untuk siklus ini.")
                            continue
                        await asyncio.sleep(2)

                        sell_qty = initial_quantity * partial_tp_percent
                        sell_order = client.place_market_sell_order(symbol, sell_qty)
                        if not sell_order:
                            print(f"  >> SANGAT KRITIS: Gagal menjual partial TP untuk {symbol}. Periksa manual!")
                            continue

                        new_remaining_qty = remaining_quantity - float(sell_order['executedQty'])
                        position['remaining_quantity'] = new_remaining_qty
                        position['partial_tps_taken'].append(tp_level)
                        
                        print(f"  >> SUKSES: Berhasil menjual {sell_order['executedQty']} {symbol}. Sisa: {new_remaining_qty}")

                        if new_remaining_qty > 0.00001:
                            sl_mapping_targets = {0: buy_price}
                            for t in signal_targets: sl_mapping_targets[t['level']] = t['price']
                            
                            new_sl_level = config.TRAILING_CONFIG.get(str(tp_level), None)
                            new_sl_price = sl_mapping_targets.get(new_sl_level, position['signal_data']['stop_loss'])
                            final_tp_price = max(t['price'] for t in signal_targets)

                            print(f"  >> Memasang OCO baru untuk sisa aset. SL di: ${new_sl_price:.4f}, TP di: ${final_tp_price:.4f}")
                            new_oco = client.place_oco_sell_order(symbol, new_remaining_qty, final_tp_price, new_sl_price, new_sl_price * 0.998)
                            
                            if new_oco:
                                position['order_list_id'] = new_oco.get('orderListId')
                                print(f"  >> SUKSES: OCO baru untuk {symbol} berhasil dipasang.")
                            else:
                                print(f"  >> SANGAT KRITIS: Gagal memasang OCO baru untuk {symbol}!")
                        else:
                            print(f"  >> INFO: Seluruh posisi {symbol} telah terjual. Menghapus dari DB.")
                            mongo.delete_open_position(symbol)

                        mongo.save_open_position(position)
                        break
                
        except Exception as e:
            import traceback
            print(f"  - LOG ERROR: Terjadi kesalahan tak terduga saat memproses {symbol}. Error: {e}", file=sys.stderr)
            traceback.print_exc()
            continue
        
    mongo.close_connection()
    print("\n--- Rutinitas Manajemen Posisi Selesai ---")

async def run_autoloop_routine(duration_minutes: int, message_limit: int, cycle_delay_seconds: int, initial_fetch_limit: int):
    """Menjalankan bot dalam loop otomatis untuk durasi tertentu."""
    end_time = time.time() + duration_minutes * 60 if duration_minutes > 0 else None
    cycle_count = 0
    while True:
        if end_time and time.time() >= end_time:
            print("Durasi autoloop telah selesai. Bot berhenti.")
            break
            
        cycle_count += 1
        print(f"\n{'='*15} Memulai Siklus Otomatis #{cycle_count} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) {'='*15}")
        try:
            await run_fetch_routine(message_limit=initial_fetch_limit if cycle_count == 1 else message_limit)
            run_decide_routine()
            run_execute_routine()
            await run_manage_positions_routine()
            run_status_routine()
        except Exception as e:
            print(f"Error fatal pada siklus utama: {e}", file=sys.stderr)
        
        if end_time and time.time() >= end_time: break
        
        print(f"\nSiklus #{cycle_count} selesai. Menunggu {cycle_delay_seconds} detik sebelum siklus berikutnya...")
        try:
            await asyncio.sleep(cycle_delay_seconds)
        except asyncio.CancelledError:
            print("\nAutoloop dihentikan secara manual.")
            break