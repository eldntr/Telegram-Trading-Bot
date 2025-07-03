# core/services.py

import time
import asyncio
import json
import os
import config
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

# Import dari komponen aplikasi Anda
from telegram.client import TelegramClientWrapper
from telegram.parser import TelegramMessageParser
from db.mongo_client import MongoManager
from binance.client import BinanceClient
from binance.strategy import TradingStrategy
from binance.trader import Trader
from binance.account import AccountManager
from telegram.utils import JsonWriter

# --- Service Layer ---
# Kelas-kelas di bawah ini memisahkan logika bisnis menjadi unit-unit yang kohesif.

class SignalService:
    """
    Bertanggung jawab untuk semua operasi terkait sinyal:
    - Menghubungkan ke Telegram.
    - Mengambil pesan.
    - Mem-parsing pesan menjadi data terstruktur.
    - Menyimpan sinyal ke database dan file JSON.
    """
    def __init__(self, client_wrapper: TelegramClientWrapper, parser: TelegramMessageParser, mongo: MongoManager):
        self.client_wrapper = client_wrapper
        self.parser = parser
        self.mongo = mongo
        self.writer = JsonWriter("parsed_messages.json")
        self.signal_writer = JsonWriter("new_signals.json")

    async def fetch_and_save_signals(self, limit: int = 50):
        """
        Menjalankan alur lengkap: fetch, parse, dan simpan sinyal dari Telegram.
        """
        print(f"Memulai pengambilan {limit} pesan dari Telegram...")
        parsed_data = []
        try:
            # Pastikan klien terhubung sebelum digunakan
            if not self.client_wrapper.is_connected():
                await self.client_wrapper.connect()

            messages = await self.client_wrapper.fetch_historical_messages(config.TARGET_CHAT_ID, limit=limit)
            if not messages:
                print("Tidak ada pesan baru yang diambil dari Telegram.")
                return

            parsed_data = [self.parser.parse_message(msg).to_dict() for msg in messages]
            self.writer.write(parsed_data) # Simpan semua pesan yang di-parse

            # Filter hanya untuk sinyal baru
            new_signals = [m for m in parsed_data if m.get("message_type") == "NewSignal"]
            if new_signals:
                self.signal_writer.write(new_signals)
                self.mongo.save_new_signals(new_signals)
            else:
                print("Tidak ada sinyal trading baru yang ditemukan di antara pesan yang diambil.")

        except Exception as e:
            print(f"❌ Terjadi error dalam rutinitas fetch sinyal: {e}")
        # Koneksi Telegram tidak ditutup di sini agar bisa digunakan kembali dalam mode autoloop


class TradingService:
    """
    Mengelola semua logika yang berhubungan dengan aktivitas trading:
    - Membuat keputusan trading (evaluasi sinyal).
    - Mengeksekusi order (buy/sell).
    - Mengelola posisi yang sedang berjalan (trailing stop loss, stuck trades).
    """
    def __init__(self, strategy: TradingStrategy, trader: Trader, account_manager: AccountManager, mongo: MongoManager, binance_client: BinanceClient):
        self.strategy = strategy
        self.trader = trader
        self.account_manager = account_manager
        self.mongo = mongo
        self.binance_client = binance_client
        self.decisions_writer = JsonWriter("trade_decisions.json")
        self.log_writer = JsonWriter("trade_log.json")

    def decide_from_new_signals(self) -> List[Dict[str, Any]]:
        """
        Mengambil sinyal baru dari DB, mengevaluasinya menggunakan strategi,
        dan menyimpan keputusan trading.
        """
        if not all([config.BINANCE_API_KEY, config.BINANCE_API_SECRET]):
            print("Kunci API Binance tidak dikonfigurasi. Melewatkan rutinitas keputusan.")
            return []

        new_signals = self.mongo.get_all_new_signals()
        if not new_signals:
            print("Tidak ada sinyal baru untuk dievaluasi dari DB.")
            return []

        print(f"Mengevaluasi {len(new_signals)} sinyal baru...")
        all_decisions = [self.strategy.evaluate_new_signal(signal).to_dict() for signal in new_signals]

        self.decisions_writer.write(all_decisions)
        buy_count = sum(1 for d in all_decisions if d.get('decision') == 'BUY')
        print(f"✅ Berhasil membuat {len(all_decisions)} keputusan trading. [{buy_count} BUY, {len(all_decisions) - buy_count} SKIP]")
        return all_decisions

    def execute_approved_trades(self, decisions_data: Optional[List[Dict[str, Any]]] = None):
        """
        Mengeksekusi semua keputusan trading yang disetujui ('BUY').
        """
        if not all([config.BINANCE_API_KEY, config.BINANCE_API_SECRET]):
            print("Kunci API Binance tidak dikonfigurasi. Melewatkan eksekusi.")
            return

        # Jika data keputusan tidak diberikan sebagai argumen, baca dari file
        if decisions_data is None:
            try:
                with open(os.path.join("data", "trade_decisions.json"), 'r') as f:
                    decisions_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                print("File trade_decisions.json tidak ditemukan atau kosong. Tidak ada yang dieksekusi.")
                return

        buy_decisions = [d for d in decisions_data if d.get('decision') == 'BUY']
        if not buy_decisions:
            print("Tidak ditemukan keputusan 'BUY'. Tidak ada yang dieksekusi.")
            return

        print(f"Ditemukan {len(buy_decisions)} keputusan 'BUY' untuk dieksekusi.")
        trade_logs = []
        account_summary = self.account_manager.get_account_summary()
        if not account_summary:
            print("❌ Gagal mengambil summary akun, eksekusi dihentikan.")
            return

        for decision in buy_decisions:
            result = self.trader.execute_trade(decision, account_summary)
            trade_logs.append({"decision_details": decision, "execution_result": result})

            # Jika trade berhasil, simpan posisi ke DB untuk manajemen lebih lanjut
            if result.get('status') == 'SUCCESS':
                buy_order = result.get('buy_order', {})
                oco_order = result.get('oco_order', {})
                if buy_order and oco_order:
                    # Hitung harga beli rata-rata
                    executed_qty = float(buy_order.get('executedQty', 0))
                    cummulative_quote_qty = float(buy_order.get('cummulativeQuoteQty', 0))
                    avg_price = cummulative_quote_qty / executed_qty if executed_qty > 0 else 0
                    
                    position_doc = {
                        "coin_pair": buy_order.get('symbol'),
                        "buy_price": avg_price,
                        "quantity": executed_qty,
                        "order_list_id": oco_order.get('orderListId'),
                        "signal_data": decision.get('parsed_signal', {}),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "last_tp_level_hit": 0 # TP Level terakhir yang tercapai
                    }
                    self.mongo.save_open_position(position_doc)
                # Beri jeda antar eksekusi untuk menghindari rate limit API
                time.sleep(2)

        if trade_logs:
            self.log_writer.write(trade_logs)

    async def manage_open_positions(self):
        """
        Mengelola posisi aktif: Trailing Stop Loss & penutupan posisi macet.
        """
        if not all([config.BINANCE_API_KEY, config.BINANCE_API_SECRET]):
            print("Manajemen posisi dilewati: Kunci API tidak ditemukan.")
            return

        db_positions = self.mongo.get_all_open_positions()
        if not db_positions:
            print("Tidak ada posisi aktif yang dilacak di DB untuk dikelola.")
            return

        active_binance_orders = self.binance_client.get_open_orders()
        active_order_map = {o['symbol']: o for o in active_binance_orders if o.get('orderListId', -1) != -1}

        print(f"Memeriksa {len(db_positions)} posisi yang dilacak di DB...")
        for pos in db_positions:
            symbol = pos['coin_pair']

            # 1. Sinkronisasi: Periksa apakah posisi masih ada di Binance
            if pos.get('order_list_id') not in [o.get('orderListId') for o in active_binance_orders]:
                print(f"  -  pozycji {symbol} sudah tertutup di Binance. Menghapus dari pelacakan DB.")
                self.mongo.delete_open_position(symbol)
                await asyncio.sleep(1) # Jeda singkat
                continue

            print(f"\n- Memeriksa posisi aktif: {symbol}...")
            await self._handle_trailing_stop(pos)
            await self._handle_stuck_trade(pos)

    async def _handle_trailing_stop(self, position: Dict[str, Any]):
        """Logika untuk menyesuaikan Stop Loss (Trailing SL) saat target profit tercapai."""
        symbol = position['coin_pair']
        signal_data = position.get('signal_data', {})
        take_profits = signal_data.get('take_profits', [])
        
        current_price = self.binance_client.get_current_price(symbol)
        if not current_price:
            print(f"  - Tidak bisa mendapatkan harga terkini untuk {symbol}. Melewatkan.")
            return

        last_tp_hit = position.get('last_tp_level_hit', 0)
        new_tp_level_to_hit = last_tp_hit + 1

        if new_tp_level_to_hit > len(take_profits):
            # Semua TP sudah tercapai, seharusnya order sudah tertutup
            return

        target_tp = take_profits[new_tp_level_to_hit - 1]
        if current_price >= target_tp['price']:
            print(f"  🚀 TP{new_tp_level_to_hit} untuk {symbol} tercapai! Harga: {current_price} >= Target: {target_tp['price']}")
            
            # Tentukan stop loss baru. Aturan: SL baru = Entry Price jika TP1, TP1 jika TP2, dst.
            new_stop_loss = signal_data['entry_prices'][0]['from'] if new_tp_level_to_hit == 1 else take_profits[new_tp_level_to_hit - 2]['price']
            
            # Batalkan OCO order lama
            print(f"  - Membatalkan OCO order lama (ID: {position['order_list_id']})...")
            self.binance_client.cancel_order_by_list_id(symbol, position['order_list_id'])
            await asyncio.sleep(2) # Beri jeda setelah pembatalan
            
            # Buat OCO order baru dengan SL yang diperbarui
            print(f"  - Membuat OCO order baru. SL baru: {new_stop_loss}")
            new_oco_order = self.trader.create_oco_order(
                symbol=symbol,
                quantity=position['quantity'],
                take_profit_price=take_profits[-1]['price'], # Selalu targetkan TP terakhir
                stop_loss_price=new_stop_loss,
                stop_loss_limit_price=new_stop_loss * 0.998 # Harga limit sedikit di bawah stop
            )

            if new_oco_order:
                # Update data posisi di DB
                position['order_list_id'] = new_oco_order['orderListId']
                position['last_tp_level_hit'] = new_tp_level_to_hit
                self.mongo.save_open_position(position)
                print(f"  ✅ Trailing Stop Loss untuk {symbol} berhasil diperbarui.")
            else:
                print(f"  ❌ GAGAL membuat OCO order baru untuk {symbol}. Posisi mungkin perlu ditangani manual.")


    async def _handle_stuck_trade(self, position: Dict[str, Any]):
        """Logika untuk menutup paksa trade yang macet (tidak bergerak dalam waktu lama)."""
        symbol = position['coin_pair']
        time_since_open = datetime.now(timezone.utc) - datetime.fromisoformat(position['timestamp'])
        
        # Aturan: jika posisi terbuka lebih dari 24 jam dan belum mencapai TP1
        if time_since_open > timedelta(hours=config.STUCK_TRADE_HOURS_THRESHOLD) and position.get('last_tp_level_hit', 0) == 0:
            print(f"  - ⚠️ PERINGATAN: Posisi {symbol} terdeteksi macet ({time_since_open.total_seconds() / 3600:.1f} jam). Menutup posisi...")
            
            # 1. Batalkan OCO order yang ada
            print(f"  - Membatalkan OCO order lama (ID: {position['order_list_id']})...")
            self.binance_client.cancel_order_by_list_id(symbol, position['order_list_id'])
            await asyncio.sleep(2) # Jeda
            
            # 2. Jual di harga pasar
            print(f"  - Mengeksekusi MARKET SELL untuk {position['quantity']} {symbol}...")
            sell_result = self.binance_client.create_market_order(symbol, 'SELL', position['quantity'])
            
            if sell_result:
                print(f"  ✅ Posisi macet {symbol} berhasil ditutup.")
                self.mongo.delete_open_position(symbol)
            else:
                print(f"  ❌ GAGAL menutup posisi macet {symbol}. Perlu pengecekan manual.")


class AccountService:
    """
    Menyediakan layanan terkait informasi akun Binance:
    - Pengecekan saldo.
    - Pengecekan order terbuka.
    """
    def __init__(self, account_manager: AccountManager):
        self.account_manager = account_manager
        self.status_writer = JsonWriter("account_status.json")
        self.orders_writer = JsonWriter("open_orders_status.json")

    def check_and_save_status(self):
        """
        Memeriksa status akun (saldo) dan order terbuka, lalu menyimpannya ke file.
        """
        if not all([config.BINANCE_API_KEY, config.BINANCE_API_SECRET]):
            print("Kunci API tidak ditemukan. Melewatkan pengecekan status.")
            return

        print("\n[1/2] Memeriksa Saldo Aset...")
        summary = self.account_manager.get_account_summary()
        if summary:
            self.status_writer.write(summary)
            print(f"✅ Total Estimasi Nilai Akun: ${summary.get('total_balance_usdt', 0):.2f}")
            print(f"   USDT Tersedia: {summary.get('usdt_free', 0):.2f}")
        else:
            print("❌ Gagal mengambil data saldo.")

        print("\n[2/2] Memeriksa Transaksi Berjalan (Open Orders)...")
        open_orders = self.account_manager.client.get_open_orders()
        if not open_orders:
            print("Tidak ada transaksi berjalan (order aktif) yang ditemukan.")
        else:
            print(f"Ditemukan {len(open_orders)} order aktif.")
            # Proses data agar lebih mudah dibaca
            processed = [
                {
                    "symbol": o.get('symbol'), "type": o.get('type'), "side": o.get('side'),
                    "quantity": o.get('origQty'), "price": o.get('price'), "stopPrice": o.get('stopPrice'),
                    "orderListId": o.get('orderListId', -1)
                } for o in open_orders
            ]
            self.orders_writer.write(processed)