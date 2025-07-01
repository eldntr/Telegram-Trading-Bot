# test_sl_filter.py (Diperbarui dengan Skenario Tes Riil)

import unittest
import os
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone

# Atur config sebelum import modul lain agar nilainya benar
import config
config.AVOID_BUYING_AFTER_SL = True
config.SIGNAL_VALIDITY_MINUTES = 45

from binance.strategy import TradingStrategy
from binance.client import BinanceClient
from binance.models import TradeDecision

class TestRecentSLFilter(unittest.TestCase):

    def setUp(self):
        """Disiapkan sebelum setiap tes."""
        self.mock_binance_client = Mock(spec=BinanceClient)
        # Mock fungsi-fungsi lain yang dipanggil oleh strategy
        self.mock_binance_client.get_current_price.return_value = 100.0
        # Data klines dummy yang cukup untuk lolos dari filter tren
        self.mock_binance_client.get_klines.return_value = [[0, 0, 0, 0, float(i), 0] for i in range(90, 110)]
        
        self.strategy = TradingStrategy(self.mock_binance_client)
        
        # Sinyal dummy yang akan digunakan di semua tes
        self.sample_signal = {
            "coin_pair": "DUMMYUSDT",
            "risk_level": "Normal",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry_price": 105.0,
            "targets": [{"level": 1, "price": 110.0}],
            "stop_losses": [{"level": 1, "price": 95.0}]
        }

    def test_01_should_fail_if_recent_sl_found(self):
        """Tes Kasus 1: GAGAL jika ada SL terpicu 10 menit lalu (data mock)."""
        print("\n--- Menjalankan Tes 1: Gagal karena ada SL baru ---")
        
        ten_minutes_ago_ms = int((datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp() * 1000)
        mock_orders = [{"symbol": "DUMMYUSDT", "type": "STOP_LOSS_LIMIT", "status": "FILLED", "updateTime": ten_minutes_ago_ms}]
        self.mock_binance_client.get_all_orders.return_value = mock_orders

        decision = self.strategy.evaluate_new_signal(self.sample_signal)

        self.assertEqual(decision.decision, "FAIL")
        self.assertIn("Stop Loss terdeteksi", decision.reason)
        print("✅ Tes Berhasil: Keputusan adalah 'FAIL' seperti yang diharapkan.")

    def test_02_should_pass_if_sl_is_old(self):
        """Tes Kasus 2: LOLOS jika SL terakhir sudah lama (data mock)."""
        print("\n--- Menjalankan Tes 2: Lolos karena SL sudah lama ---")
        
        two_hours_ago_ms = int((datetime.now(timezone.utc) - timedelta(minutes=120)).timestamp() * 1000)
        mock_orders = [{"symbol": "DUMMYUSDT", "type": "STOP_LOSS_LIMIT", "status": "FILLED", "updateTime": two_hours_ago_ms}]
        self.mock_binance_client.get_all_orders.return_value = mock_orders

        with patch('binance.strategy.TradingStrategy._analyze_asset_condition') as mock_analyze:
            mock_analyze.return_value = {"is_above_sma": True, "error": None, "warning": None}
            decision = self.strategy.evaluate_new_signal(self.sample_signal)

        self.assertEqual(decision.decision, "BUY")
        print("✅ Tes Berhasil: Keputusan adalah 'BUY' karena SL lama diabaikan.")

    def test_03_should_pass_if_no_sl_history(self):
        """Tes Kasus 3: LOLOS jika tidak ada riwayat SL sama sekali (data mock)."""
        print("\n--- Menjalankan Tes 3: Lolos karena tidak ada riwayat SL ---")
        
        self.mock_binance_client.get_all_orders.return_value = []
        
        with patch('binance.strategy.TradingStrategy._analyze_asset_condition') as mock_analyze:
            mock_analyze.return_value = {"is_above_sma": True, "error": None, "warning": None}
            decision = self.strategy.evaluate_new_signal(self.sample_signal)

        self.assertEqual(decision.decision, "BUY")
        print("✅ Tes Berhasil: Keputusan adalah 'BUY' karena tidak ada riwayat SL.")
        
    def test_04_should_pass_if_feature_is_disabled(self):
        """Tes Kasus 4: LOLOS jika fitur dinonaktifkan di config."""
        print("\n--- Menjalankan Tes 4: Lolos karena fitur dimatikan ---")
        
        config.AVOID_BUYING_AFTER_SL = False
        
        with patch('binance.strategy.TradingStrategy._analyze_asset_condition') as mock_analyze:
            mock_analyze.return_value = {"is_above_sma": True, "error": None, "warning": None}
            decision = self.strategy.evaluate_new_signal(self.sample_signal)

        self.assertEqual(decision.decision, "BUY")
        self.strategy.client.get_all_orders.assert_not_called()
        print("✅ Tes Berhasil: Keputusan 'BUY' karena fitur nonaktif.")
        
        config.AVOID_BUYING_AFTER_SL = True

    @unittest.skipIf(not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET, 
                     "Kunci API Binance tidak diatur, tes koneksi asli dilewati.")
    def test_05_real_api_connection(self):
        """Tes Kasus 5: Memastikan koneksi ke API Binance asli berhasil."""
        print("\n--- Menjalankan Tes 5: Koneksi API Binance Asli ---")
        print("ℹ️  Tes ini akan terhubung ke akun Binance Anda (read-only).")

        real_client = BinanceClient(api_key=config.BINANCE_API_KEY, api_secret=config.BINANCE_API_SECRET)
        
        try:
            recent_orders = real_client.get_all_orders(symbol="BTCUSDT", limit=5)
        except Exception as e:
            self.fail(f"Terjadi error saat menghubungi API Binance: {e}")

        self.assertIsNotNone(recent_orders)
        self.assertIsInstance(recent_orders, list)

        if recent_orders:
            print(f"✅ Tes Berhasil: Sukses mengambil {len(recent_orders)} order terakhir dari Binance.")
        else:
            print("✅ Tes Berhasil: Koneksi sukses, namun tidak ada riwayat order ditemukan.")

    # --- TES BARU: Skenario dengan Data Riil Anda ---
    def test_06_real_hftusdt_scenario(self):
        """
        Tes Kasus 6: Mensimulasikan keputusan Beli/Tolak berdasarkan data riil HFTUSDT.
        Logika:
        1. Ada riwayat SL yang terisi (FILLED).
        2. Tes akan memodifikasi timestamp SL tersebut menjadi 'baru saja terjadi'.
        3. Bot harus memutuskan 'FAIL' (Tolak Beli).
        """
        print("\n--- Menjalankan Tes 6: Skenario Riil dengan Data HFTUSDT ---")

        # Data riil yang Anda berikan
        real_hftusdt_orders = [
            {'symbol': 'HFTUSDT', 'orderId': 780365379, 'orderListId': 11147480755, 'clientOrderId': 'UywuiFVcWgEHbmo4cfjont', 'price': '0.12630000', 'origQty': '237.60000000', 'executedQty': '237.60000000', 'cummulativeQuoteQty': '30.12768000', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'STOP_LOSS_LIMIT', 'side': 'SELL', 'stopPrice': '0.12700000', 'time': 1751402768863, 'updateTime': 1751404636275, 'isWorking': True},
            {'symbol': 'HFTUSDT', 'orderId': 780365380, 'orderListId': 11147480755, 'clientOrderId': 'FkxoRu3cv7JZdag2hJdzMA', 'price': '0.24310000', 'origQty': '237.60000000', 'executedQty': '0.00000000', 'status': 'EXPIRED', 'timeInForce': 'GTC', 'type': 'LIMIT_MAKER', 'side': 'SELL', 'time': 1751402768863, 'updateTime': 1751404636275, 'isWorking': True},
            {'symbol': 'HFTUSDT', 'orderId': 780631749, 'orderListId': -1, 'clientOrderId': 'HZRowHae4AEd1KljKQtN8I', 'price': '0.00000000', 'origQty': '263.30000000', 'executedQty': '263.30000000', 'cummulativeQuoteQty': '34.99257000', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'MARKET', 'side': 'BUY', 'time': 1751405128726, 'updateTime': 1751405128726, 'isWorking': True},
            {'symbol': 'HFTUSDT', 'orderId': 780631863, 'orderListId': 11147919008, 'clientOrderId': 'ijt3s1VBDpjy8eRbETGZTf', 'price': '0.12630000', 'origQty': '263.30000000', 'executedQty': '0.00000000', 'status': 'NEW', 'timeInForce': 'GTC', 'type': 'STOP_LOSS_LIMIT', 'side': 'SELL', 'time': 1751405130974, 'updateTime': 1751405130974, 'isWorking': False},
            {'symbol': 'HFTUSDT', 'orderId': 780631864, 'orderListId': 11147919008, 'clientOrderId': '8Uq80lPoIyP5IXPDjgM6Sl', 'price': '0.24310000', 'origQty': '263.30000000', 'executedQty': '0.00000000', 'status': 'NEW', 'timeInForce': 'GTC', 'type': 'LIMIT_MAKER', 'side': 'SELL', 'time': 1751405130974, 'updateTime': 1751405130974, 'isWorking': True}
        ]
        
        # --- SKENARIO 1: SL terjadi BARU SAJA ---
        print("  -> Skenario A: Mensimulasikan SL terjadi 5 menit yang lalu.")
        
        # Modifikasi timestamp pada data riil agar relevan dengan waktu saat ini
        five_minutes_ago_ms = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp() * 1000)
        real_hftusdt_orders[0]['updateTime'] = five_minutes_ago_ms # Ubah waktu SL yang FILLED

        # Arahkan mock client untuk menggunakan data riil yang sudah dimodifikasi ini
        self.mock_binance_client.get_all_orders.return_value = real_hftusdt_orders

        # Buat sinyal khusus untuk HFTUSDT
        hft_signal = self.sample_signal.copy()
        hft_signal['coin_pair'] = "HFTUSDT"
        
        # Evaluasi sinyal
        decision = self.strategy.evaluate_new_signal(hft_signal)

        # Verifikasi: Keputusan harus GAGAL karena ada SL yang baru
        self.assertEqual(decision.decision, "FAIL", "Bot seharusnya menolak pembelian karena ada SL baru.")
        self.assertIn("Stop Loss terdeteksi", decision.reason)
        print("✅ Tes Skenario A Berhasil: Pembelian HFTUSDT ditolak karena riwayat SL terdeteksi.")

        # --- SKENARIO 2: SL terjadi SUDAH LAMA ---
        print("\n  -> Skenario B: Mensimulasikan SL terjadi 2 jam yang lalu.")
        
        # Modifikasi timestamp SL menjadi di luar periode validitas
        two_hours_ago_ms = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp() * 1000)
        real_hftusdt_orders[0]['updateTime'] = two_hours_ago_ms

        self.mock_binance_client.get_all_orders.return_value = real_hftusdt_orders

        # Evaluasi ulang sinyal dengan data yang sama tapi waktu SL yang berbeda
        decision = self.strategy.evaluate_new_signal(hft_signal)
        
        # Verifikasi: Keputusan harus LOLOS (BUY) karena SL sudah lama
        self.assertEqual(decision.decision, "BUY", "Bot seharusnya mengizinkan pembelian karena SL sudah lama.")
        print("✅ Tes Skenario B Berhasil: Pembelian HFTUSDT diizinkan karena riwayat SL sudah kedaluwarsa.")


if __name__ == '__main__':
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("Peringatan: python-dotenv tidak terinstall. Beberapa tes mungkin gagal.")
    
    import importlib
    importlib.reload(config)

    unittest.main(verbosity=2)