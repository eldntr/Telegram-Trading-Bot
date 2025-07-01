# test_sl_filter.py (FINAL - Diperbaiki untuk semua kegagalan)

import unittest
import os
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone

# Atur config sebelum import modul lain agar nilainya benar
import config
config.AVOID_BUYING_AFTER_SL = True
config.SIGNAL_VALIDITY_MINUTES = 45
config.MAX_SL_PERCENTAGE_ENABLED = True
config.MAX_SL_PERCENTAGE = -5.0 # Batas default untuk tes

from binance.strategy import TradingStrategy
from binance.client import BinanceClient

class TestRecentSLFilter(unittest.TestCase):
    """Tes untuk fitur "hindari membeli setelah SL"."""
    def setUp(self):
        self.mock_binance_client = Mock(spec=BinanceClient)
        self.strategy = TradingStrategy(self.mock_binance_client)
        self.sample_signal = {
            "coin_pair": "DUMMYUSDT", "risk_level": "Normal",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry_price": 105.0, "targets": [{"level": 1, "price": 110.0}],
            "stop_losses": [{"level": 1, "price": 95.0}]
        }
        self.patcher = patch('binance.strategy.TradingStrategy._analyze_asset_condition')
        self.mock_analyze = self.patcher.start()
        self.mock_analyze.return_value = {"is_above_sma": True, "error": None}
        self.mock_binance_client.get_current_price.return_value = 100.0

    def tearDown(self):
        self.patcher.stop()

    @patch('binance.strategy.TradingStrategy._check_for_recent_sl')
    def test_01_should_fail_if_recent_sl_found(self, mock_check_sl):
        print("\n--- Menjalankan Tes Riwayat SL: Gagal karena ada SL baru ---")
        mock_check_sl.return_value = True
        config.MAX_SL_PERCENTAGE_ENABLED = False
        decision = self.strategy.evaluate_new_signal(self.sample_signal)
        mock_check_sl.assert_called_once_with("DUMMYUSDT")
        self.assertEqual(decision.decision, "FAIL")
        self.assertIn("Pembelian dicegah karena SL terdeteksi", decision.reason)
        config.MAX_SL_PERCENTAGE_ENABLED = True
        print("✅ Tes Berhasil: Keputusan adalah 'FAIL' karena riwayat SL.")

    @patch('binance.strategy.TradingStrategy._check_for_recent_sl')
    def test_02_should_pass_if_sl_is_old(self, mock_check_sl):
        print("\n--- Menjalankan Tes Riwayat SL: Lolos karena SL sudah lama/tidak ada ---")
        mock_check_sl.return_value = False
        config.MAX_SL_PERCENTAGE_ENABLED = False
        decision = self.strategy.evaluate_new_signal(self.sample_signal)
        self.assertEqual(decision.decision, "BUY")
        config.MAX_SL_PERCENTAGE_ENABLED = True
        print("✅ Tes Berhasil: Keputusan adalah 'BUY'.")

    def test_04_should_pass_if_feature_is_disabled(self):
        print("\n--- Menjalankan Tes Riwayat SL: Lolos karena fitur dimatikan ---")
        config.AVOID_BUYING_AFTER_SL = False
        config.MAX_SL_PERCENTAGE_ENABLED = False
        decision = self.strategy.evaluate_new_signal(self.sample_signal)
        self.assertEqual(decision.decision, "BUY")
        config.AVOID_BUYING_AFTER_SL = True
        config.MAX_SL_PERCENTAGE_ENABLED = True
        print("✅ Tes Berhasil: Keputusan 'BUY' karena fitur riwayat SL nonaktif.")

    def test_06_real_hftusdt_scenario_sl_history(self):
        print("\n--- Menjalankan Tes Riwayat SL: Skenario Riil HFTUSDT ---")
        config.MAX_SL_PERCENTAGE_ENABLED = False
        five_minutes_ago_ms = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp() * 1000)
        self.mock_binance_client.get_all_orders.return_value = [{'symbol': 'HFTUSDT', 'type': 'STOP_LOSS_LIMIT', 'status': 'FILLED', 'updateTime': five_minutes_ago_ms}]
        hft_signal = self.sample_signal.copy()
        hft_signal['coin_pair'] = "HFTUSDT"
        decision = self.strategy.evaluate_new_signal(hft_signal)
        self.assertEqual(decision.decision, "FAIL")
        self.assertIn("Pembelian dicegah karena SL terdeteksi", decision.reason)
        config.MAX_SL_PERCENTAGE_ENABLED = True
        print("✅ Tes Berhasil: Pembelian HFTUSDT ditolak karena riwayat SL terdeteksi.")


@unittest.skipIf(not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET, "Kunci API tidak diatur, tes koneksi asli dilewati.")
class TestRealAPIConnection(unittest.TestCase):
    def test_05_real_api_connection(self):
        print("\n--- Menjalankan Tes 5: Koneksi API Binance Asli ---")
        real_client = BinanceClient(api_key=config.BINANCE_API_KEY, api_secret=config.BINANCE_API_SECRET)
        try:
            recent_orders = real_client.get_all_orders(symbol="BTCUSDT", limit=5)
            self.assertIsNotNone(recent_orders)
            print("✅ Tes Berhasil: Sukses terhubung ke Binance.")
        except Exception as e:
            self.fail(f"Error saat menghubungi API Binance: {e}")

class TestMaxSLFilter(unittest.TestCase):
    def setUp(self):
        # --- PERBAIKAN UTAMA DI SINI ---
        self.mock_binance_client = Mock(spec=BinanceClient)
        self.strategy = TradingStrategy(self.mock_binance_client)
        # Mock harga saat ini agar validasi harga lolos
        self.mock_binance_client.get_current_price.return_value = 100.0
        
        # Matikan filter lain untuk isolasi tes
        config.AVOID_BUYING_AFTER_SL = False
        config.FILTER_OLD_SIGNALS_ENABLED = False
        
        self.patcher = patch('binance.strategy.TradingStrategy._analyze_asset_condition')
        self.mock_analyze = self.patcher.start()
        self.mock_analyze.return_value = {"is_above_sma": True, "error": None}

    def tearDown(self):
        self.patcher.stop()
        # Kembalikan config ke keadaan semula
        config.AVOID_BUYING_AFTER_SL = True
        config.FILTER_OLD_SIGNALS_ENABLED = True

    def create_test_signal(self, sl_price):
        return {"coin_pair": "TESTUSDT", "entry_price": 100.0, "stop_losses": [{"level": 1, "price": sl_price}], "targets": [{"level": 1, "price": 110.0}], "risk_level": "Normal", "timestamp": datetime.now(timezone.utc).isoformat()}

    def test_sl_within_limit_should_pass(self):
        print("\n--- Menjalankan Tes SL Filter: SL dalam batas ---")
        config.MAX_SL_PERCENTAGE_ENABLED = True
        config.MAX_SL_PERCENTAGE = -5.0
        signal = self.create_test_signal(sl_price=96.0)
        decision = self.strategy.evaluate_new_signal(signal)
        self.assertEqual(decision.decision, "BUY")
        print("✅ Tes Berhasil: Keputusan 'BUY' karena SL -4.00% <= -5.00%")

    def test_sl_exceeds_limit_should_fail(self):
        print("\n--- Menjalankan Tes SL Filter: SL melebihi batas ---")
        config.MAX_SL_PERCENTAGE_ENABLED = True
        config.MAX_SL_PERCENTAGE = -5.0
        signal = self.create_test_signal(sl_price=93.0)
        decision = self.strategy.evaluate_new_signal(signal)
        self.assertEqual(decision.decision, "FAIL")
        print("✅ Tes Berhasil: Keputusan 'FAIL' karena SL -7.00% > -5.00%")

    def test_filter_disabled_should_pass(self):
        print("\n--- Menjalankan Tes SL Filter: Fitur dimatikan ---")
        config.MAX_SL_PERCENTAGE_ENABLED = False
        signal = self.create_test_signal(sl_price=93.0)
        decision = self.strategy.evaluate_new_signal(signal)
        self.assertEqual(decision.decision, "BUY")
        config.MAX_SL_PERCENTAGE_ENABLED = True
        print("✅ Tes Berhasil: Keputusan 'BUY' karena filter SL nonaktif.")

if __name__ == '__main__':
    unittest.main(verbosity=2)