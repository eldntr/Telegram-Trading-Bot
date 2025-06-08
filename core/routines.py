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
    """
    Fungsi eksekusi dengan logika pengecekan pra-swap.
    """
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
    account_summary = manager.get_account_summary()
    if not account_summary: 
        mongo.close_connection()
        return

    if not config.PRIORITIZE_NORMAL_RISK:
        print("Mode Prioritas Risiko NON-AKTIF. Mengeksekusi semua sinyal 'BUY'.")
        for decision in buy_decisions:
            result = trader.execute_trade(decision, account_summary)
            trade_logs.append({"decision_details": decision, "execution_result": result})
            if result.get('status') == 'SUCCESS':
                time.sleep(2)
                refreshed_summary = manager.get_account_summary()
                if refreshed_summary: account_summary = refreshed_summary
    else:
        # --- LOGIKA PRIORITAS DENGAN PENGECEKAN PRA-SWAP ---
        print("Mode Prioritas Risiko AKTIF. Mengkategorikan sinyal...")
        normal_risk_buys = [d for d in buy_decisions if d.get('risk_level', '').lower() == 'normal']
        high_risk_buys = [d for d in buy_decisions if d.get('risk_level', '').lower() == 'high']
        print(f"Ditemukan {len(normal_risk_buys)} sinyal 'Normal' dan {len(high_risk_buys)} sinyal 'High'.")

        swapped_out_symbols = set()

        stuck_high_risk_to_swap = []
        processed_symbols = set()
        print("\n[PRIO] Mencari kandidat posisi High Risk yang macet untuk ditukar...")
        open_orders = client.get_open_orders()
        if open_orders:
            for order in open_orders:
                symbol = order['symbol']
                if symbol in processed_symbols: continue
                signal_data = mongo.get_signal_by_pair(symbol)
                if signal_data and signal_data.get('risk_level', '').lower() == 'high':
                    processed_symbols.add(symbol)
                    try:
                        current_price = client.get_current_price(symbol)
                        sl_price = signal_data['stop_losses'][0]['price']
                        tp1_price = signal_data['targets'][0]['price']
                        if current_price and sl_price < current_price < tp1_price:
                            stuck_high_risk_to_swap.append(symbol)
                    except (IndexError, KeyError, TypeError): continue
        print(f"[PRIO] Ditemukan {len(stuck_high_risk_to_swap)} kandidat posisi macet: {stuck_high_risk_to_swap}")

        if normal_risk_buys:
            print("\n[PRIO] Memproses sinyal Normal Risk...")
            for decision in normal_risk_buys:
                # --- LOGIKA BARU: Pengecekan pra-swap ---
                is_buyable, reason = trader.can_execute_trade(decision, account_summary)
                
                if not is_buyable:
                    print(f"  -> Melewatkan sinyal Normal {decision['coin_pair']}: {reason}")
                    trade_logs.append({"decision_details": decision, "execution_result": {"status": "SKIP", "reason": reason}})
                    continue

                # Jika sinyal Normal BISA dibeli, baru kita pertimbangkan untuk swap
                if stuck_high_risk_to_swap:
                    symbol_to_cancel = stuck_high_risk_to_swap.pop(0)
                    print(f"\n[SWAP] Sinyal Normal {decision['coin_pair']} bisa dibeli. Mengganti posisi macet {symbol_to_cancel}...")
                    
                    cancel_res = client.cancel_all_open_orders_for_symbol(symbol_to_cancel)
                    if not cancel_res:
                        print(f"  - KRITIS: Gagal membatalkan order untuk {symbol_to_cancel}.")
                        trade_logs.append({"action": "CANCEL_FOR_SWAP_FAILED", "symbol": symbol_to_cancel})
                    else:
                        print(f"  - Sukses membatalkan order untuk {symbol_to_cancel}. Menunggu untuk likuidasi...")
                        swapped_out_symbols.add(symbol_to_cancel)
                        time.sleep(2)
                        acc_info = client.get_account_info()
                        base_asset = symbol_to_cancel.replace("USDT", "")
                        asset_balance = next((float(b['free']) for b in acc_info.get('balances', []) if b['asset'] == base_asset), 0.0)

                        if asset_balance > 0:
                            sell_res = client.place_market_sell_order(symbol_to_cancel, asset_balance)
                            if sell_res:
                                print(f"  - SUKSES: Berhasil menjual {asset_balance:.4f} {base_asset}.")
                                trade_logs.append({"action": "LIQUIDATE_FOR_SWAP_SUCCESS", "symbol": symbol_to_cancel, "result": sell_res})
                            else:
                                print(f"  - SANGAT KRITIS: Gagal menjual {base_asset} setelah order dibatalkan.")
                                trade_logs.append({"action": "LIQUIDATE_FOR_SWAP_FAILED", "symbol": symbol_to_cancel})
                        
                        account_summary = manager.get_account_summary() # Refresh summary

                # Eksekusi sinyal Normal yang sudah kita pastikan bisa dibeli
                result = trader.execute_trade(decision, account_summary)
                trade_logs.append({"decision_details": decision, "execution_result": result})
                if result.get('status') == 'SUCCESS':
                    time.sleep(2)
                    account_summary = manager.get_account_summary()

        if high_risk_buys:
            print("\n[PRIO] Memproses sinyal High Risk...")
            for decision in high_risk_buys:
                if decision['coin_pair'] in swapped_out_symbols:
                    print(f"  -> Melewatkan {decision['coin_pair']} karena baru saja dijual dalam proses swap.")
                    trade_logs.append({"action": "SKIP_REBUY_AFTER_SWAP", "symbol": decision['coin_pair']})
                    continue

                result = trader.execute_trade(decision, account_summary)
                trade_logs.append({"decision_details": decision, "execution_result": result})
                if result.get('status') == 'SUCCESS':
                    time.sleep(2)
                    account_summary = manager.get_account_summary()
                    
    if trade_logs: JsonWriter("trade_log.json").write(trade_logs)
    mongo.close_connection()
    print("\n--- Rutinitas Eksekusi Trading (Mode Prioritas) Selesai ---")

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

# ==============================================================================
# === FUNGSI YANG DIPERBAIKI ===
# ==============================================================================
async def run_manage_positions_routine():
    """
    Memeriksa semua posisi OCO yang terbuka dan menerapkan strategi manajemen.
    Versi ini lebih tangguh terhadap error data.
    """
    print("\n--- [4] Memulai Rutinitas Manajemen Posisi ---")
    
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        print("API Key/Secret Binance tidak ditemukan.")
        return

    client = BinanceClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
    mongo = MongoManager(config.MONGO_URI, config.MONGO_DB_NAME)
    
    open_orders = client.get_open_orders()
    if not open_orders:
        print("Tidak ada order terbuka yang ditemukan untuk dikelola.")
        mongo.close_connection()
        return

    oco_orders = {}
    for order in open_orders:
        if order.get('orderListId', -1) != -1:
            if order['orderListId'] not in oco_orders:
                 oco_orders[order['orderListId']] = order
    
    if not oco_orders:
        print("Tidak ada order OCO aktif yang ditemukan.")
        mongo.close_connection()
        return
        
    print(f"Ditemukan {len(oco_orders)} OCO order aktif. Memeriksa setiap posisi...")

    for order_list_id, order_sample in oco_orders.items():
        symbol = order_sample.get('symbol', 'UNKNOWN_SYMBOL')
        try:
            print(f"\n- Memeriksa {symbol} (OrderListId: {order_list_id})")

            signal_data = mongo.get_signal_by_pair(symbol)
            if not signal_data:
                print(f"  Peringatan: Tidak ditemukan data sinyal untuk {symbol} di DB. Melewatkan.")
                continue
                
            current_price = client.get_current_price(symbol)
            if current_price is None:
                print(f"  Gagal mendapatkan harga terkini untuk {symbol}. Melewatkan.")
                continue

            all_orders_in_oco = [o for o in open_orders if o.get('orderListId') == order_list_id]
            sl_order = next((o for o in all_orders_in_oco if o['type'] == 'STOP_LOSS_LIMIT'), None)

            if not sl_order:
                print(f"  Tidak dapat menemukan order STOP_LOSS_LIMIT untuk {symbol}. Melewatkan.")
                continue
            
            current_sl_price = float(sl_order['stopPrice'])
            quantity = sl_order['origQty']
            
            # --- Pengecekan Posisi Macet (Stuck Trade) ---
            if config.STUCK_TRADE_ENABLED:
                order_time_ms = order_sample.get('time', 0)
                order_datetime = datetime.fromtimestamp(order_time_ms / 1000, tz=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                elapsed_hours = (now_utc - order_datetime).total_seconds() / 3600

                print(f"  Usia order: {elapsed_hours:.2f} jam.")

                if elapsed_hours >= config.STUCK_TRADE_DURATION_HOURS:
                    targets = signal_data.get('targets', [])
                    if not targets:
                        print(f"  Info: Sinyal {symbol} tidak memiliki data target untuk cek posisi macet.")
                    else:
                        tp1_price = targets[0].get('price')
                        if tp1_price and current_price < tp1_price:
                            print(f"  >> TINDAKAN: Posisi {symbol} dianggap macet (terbuka > {config.STUCK_TRADE_DURATION_HOURS} jam & di bawah TP1). Menutup posisi...")
                            
                            cancel_result = client.cancel_oco_order(symbol, order_list_id)
                            if not cancel_result:
                                print(f"  >> KRITIS: Gagal membatalkan OCO untuk posisi macet {symbol}. Intervensi manual diperlukan.")
                                continue
                            
                            print("  Sukses membatalkan OCO. Menunggu 2 detik...")
                            await asyncio.sleep(2)
                            
                            sell_result = client.place_market_sell_order(symbol, float(quantity))
                            if not sell_result:
                                print(f"  >> SANGAT KRITIS: Gagal menjual {symbol} setelah OCO dibatalkan. Aset tidak terproteksi!")
                            else:
                                print(f"  >> SUKSES: Posisi macet {symbol} berhasil ditutup.")
                            
                            continue # Lanjut ke order berikutnya setelah menutup posisi
                        else:
                            print(f"  Posisi sudah berjalan lama, namun tidak memenuhi kriteria macet.")

            # --- Pengecekan Trailing Stop Loss ---
            if config.TRAILING_ENABLED:
                print(f"  Memeriksa trailing SL. Harga: ${current_price:.4f}, SL: ${current_sl_price:.4f}")
                new_sl_price = 0
                
                # Gunakan try-except di sini juga untuk keamanan ekstra saat looping target
                try:
                    for target in signal_data.get('targets', []):
                        if target.get('level', 0) < config.MIN_TRAILING_TP_LEVEL:
                            continue
                        
                        tp_price = target.get('price')
                        if not tp_price: continue

                        trigger_price = tp_price * (1 + config.TRAILING_TRIGGER_PERCENTAGE)
                        
                        if current_price >= trigger_price and tp_price > current_sl_price:
                            print(f"  Kondisi trailing TERPENUHI pada TP{target.get('level')} (Harga: ${tp_price:.4f})")
                            new_sl_price = max(new_sl_price, tp_price)
                except Exception as e_loop:
                    print(f"  Error saat memproses target untuk trailing {symbol}: {e_loop}")

                if new_sl_price > current_sl_price:
                    print(f"  >> TINDAKAN: Memindahkan SL untuk {symbol} dari ${current_sl_price:.4f} ke ${new_sl_price:.4f}")
                    final_tp_price = signal_data.get('targets', [{}])[-1].get('price')
                    
                    if not final_tp_price:
                         print(f"  >> KRITIS: Tidak dapat menemukan harga TP final untuk {symbol}. Pembatalan trailing.")
                         continue

                    cancel_result = client.cancel_oco_order(symbol, order_list_id)
                    if not cancel_result:
                        print(f"  >> KRITIS: Gagal membatalkan OCO lama untuk {symbol} saat trailing.")
                        continue
                    
                    print("  Sukses membatalkan OCO lama. Menunggu 2 detik...")
                    await asyncio.sleep(2)

                    print(f"  Menempatkan OCO baru: TP=${final_tp_price:.4f}, SL=${new_sl_price:.4f}")
                    new_oco_result = client.place_oco_sell_order(
                        symbol=symbol,
                        quantity=quantity,
                        take_profit_price=final_tp_price,
                        stop_loss_price=new_sl_price
                    )
                    if not new_oco_result:
                        print(f"  >> SANGAT KRITIS: Aset {symbol} tidak terproteksi setelah trailing!")
                    else:
                        print(f"  >> SUKSES: Trailing SL untuk {symbol} berhasil diterapkan.")
                else:
                    print("  Tidak ada tindakan trailing yang diperlukan.")

        except Exception as e:
            # Ini akan menangkap semua error tak terduga (termasuk yg sebelumnya) saat memproses satu order
            print(f"  LOG ERROR: Terjadi kesalahan tak terduga saat memproses order {symbol} (ID: {order_list_id}). Error: {e}. Melanjutkan ke order berikutnya.")
            continue # Lanjutkan loop ke order berikutnya
        
    mongo.close_connection()
    print("\n--- Rutinitas Manajemen Posisi Selesai ---")

async def run_autoloop_routine(duration_minutes: int, message_limit: int, cycle_delay_seconds: int, initial_fetch_limit: int): # <-- Tambah argumen baru
    end_time = None
    if duration_minutes > 0:
        print(f"--- Memulai Mode Autoloop selama {duration_minutes} menit ---")
        end_time = time.time() + duration_minutes * 60
    else:
        print("--- Memulai Mode Autoloop (Berjalan Selamanya, tekan CTRL+C untuk berhenti) ---")
    
    print(f"(Fetch awal: {initial_fetch_limit} pesan, per siklus: {message_limit} pesan, jeda: {cycle_delay_seconds} detik)") # <-- Log diperjelas

    cycle_count = 0
    while True:
        if end_time and time.time() >= end_time:
            break

        cycle_count += 1
        sisa_waktu_str = f"~{int((end_time - time.time()) / 60)} menit" if end_time else "selamanya"
        print(f"\n{'='*15} Memulai Siklus #{cycle_count} (Sisa waktu: {sisa_waktu_str}) {'='*15}")
        
        try:
            # --- LOGIKA BARU UNTUK FETCH AWAL ---
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
            time.sleep(cycle_delay_seconds)
        except KeyboardInterrupt:
            print("\nCTRL+C terdeteksi. Menghentikan autoloop...")
            break
    
    print("\n--- Mode Autoloop Dihentikan ---")