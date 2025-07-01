from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import config
from .client import BinanceClient
from .models import TradeDecision, TargetInfo, StopLossInfo
import numpy as np

class TradingStrategy:
    """
    Mengevaluasi sinyal trading dan membuat keputusan berdasarkan strategi Filter Berlapis.
    """
    def __init__(self, binance_client: BinanceClient):
        self.client = binance_client

    def _calculate_rsi(self, prices, period=14) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        deltas = np.diff(prices)
        gains = deltas * (deltas > 0)
        losses = -deltas * (deltas < 0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _analyze_asset_condition(self, symbol: str, interval: str, sma_period: int) -> Dict[str, Any]:
        """
        Menganalisis kondisi sebuah aset. Jika data terbatas (untuk koin baru),
        maka akan menggunakan parameter analisis yang dinamis.
        """
        data_to_request = sma_period + 1
        klines = self.client.get_klines(symbol=symbol, interval=interval, limit=data_to_request)
        
        candles_received = len(klines) if klines else 0
        MINIMUM_CANDLES_FOR_ANALYSIS = 15

        if candles_received < MINIMUM_CANDLES_FOR_ANALYSIS:
            return {"error": f"Data sangat minim ({candles_received} lilin), analisis dibatalkan."}

        effective_sma_period = min(sma_period, candles_received)
        warning_message = None
        if candles_received < data_to_request:
            warning_message = f"Data terbatas ({candles_received} lilin), SMA dihitung menggunakan periode {effective_sma_period}."

        close_prices = [float(k[4]) for k in klines]
        is_above_sma = close_prices[-1] >= np.mean(close_prices[-effective_sma_period:])

        return {"is_above_sma": is_above_sma, "warning": warning_message, "error": None}

    def _check_for_recent_sl(self, coin_pair: str) -> bool:
        """
        --- FUNGSI BARU ---
        Memeriksa riwayat order di Binance untuk menemukan apakah ada Stop Loss (SL)
        yang terpicu untuk koin ini dalam jangka waktu 'SIGNAL_VALIDITY_MINUTES'.
        """
        print(f"🔍 Memeriksa riwayat SL untuk {coin_pair}...")
        all_orders = self.client.get_all_orders(symbol=coin_pair, limit=50) # Ambil 50 order terakhir
        if not all_orders:
            print("Tidak ditemukan riwayat order.")
            return False

        # Cari order STOP_LOSS_LIMIT yang statusnya FILLED
        filled_sl_orders = [
            order for order in all_orders 
            if order.get('type') == 'STOP_LOSS_LIMIT' and order.get('status') == 'FILLED'
        ]

        if not filled_sl_orders:
            print("Tidak ditemukan order SL yang terisi (FILLED). Aman untuk melanjutkan.")
            return False

        # Cek timestamp dari SL terakhir yang terisi
        latest_sl_order = max(filled_sl_orders, key=lambda o: o['updateTime'])
        sl_timestamp_ms = latest_sl_order['updateTime']
        sl_time = datetime.fromtimestamp(sl_timestamp_ms / 1000, tz=timezone.utc)
        
        now = datetime.now(timezone.utc)
        time_since_sl = now - sl_time
        
        validity_minutes = timedelta(minutes=config.SIGNAL_VALIDITY_MINUTES)

        print(f"SL terakhir terdeteksi pada {sl_time.strftime('%Y-%m-%d %H:%M:%S UTC')}. ({time_since_sl.total_seconds() / 60:.1f} menit lalu)")

        if time_since_sl < validity_minutes:
            print(f"🚨 PERINGATAN: SL terdeteksi dalam periode validitas ({config.SIGNAL_VALIDITY_MINUTES} menit). Pembelian akan dicegah.")
            return True # Ada SL yang baru saja terjadi
        
        print("SL terakhir di luar periode validitas. Aman untuk melanjutkan.")
        return False


    def _validate_price_conditions(self, signal: Dict[str, Any]) -> TradeDecision:
        """
        Menjalankan validasi spesifik terkait harga (dibandingkan SL dan entry).
        """
        coin_pair = signal.get("coin_pair")
        entry_price = signal.get("entry_price")
        risk_level = signal.get("risk_level")

        current_price = self.client.get_current_price(coin_pair)
        if current_price is None:
            return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=f"Gagal mendapatkan harga {coin_pair}.")

        try:
            if current_price < signal['stop_losses'][0]['price']:
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=f"Harga saat ini ({current_price}) sudah di bawah SL1.")
        except (IndexError, KeyError, TypeError):
            return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Data SL1 tidak valid.")
        
        if current_price <= entry_price:
            targets = [TargetInfo(**t) for t in signal.get("targets", [])]
            stop_losses = [StopLossInfo(**sl) for sl in signal.get("stop_losses", [])]
            return TradeDecision(
                decision="BUY", coin_pair=coin_pair, reason=f"Harga OK ({current_price} <= {entry_price}).",
                current_price=current_price, entry_price=entry_price, targets=targets,
                stop_losses=stop_losses, risk_level=risk_level
            )
        else:
            return TradeDecision(
                decision="SKIP", coin_pair=coin_pair, reason=f"Harga terlalu tinggi ({current_price} > {entry_price}).",
                current_price=current_price, entry_price=entry_price, risk_level=risk_level
            )

    def evaluate_new_signal(self, signal: Dict[str, Any]) -> TradeDecision:
        """
        Mengevaluasi sinyal baru dengan alur yang lebih efisien dan bersih.
        """
        coin_pair = signal.get("coin_pair")
        if not coin_pair:
            return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Sinyal tidak memiliki 'coin_pair'.")

        # --- Filter 1: Risk Level ---
        if config.PRIORITIZE_NORMAL_RISK:
            risk_level = signal.get("risk_level")
            print(f"Filter Risiko diaktifkan. Memeriksa Risk Level untuk {coin_pair}: '{risk_level}'")
            if not risk_level or risk_level.strip().lower() != 'normal':
                reason = f"Sinyal dilewati karena Risk Level bukan 'Normal' (Ditemukan: {risk_level})."
                print(f"❌ {reason}")
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=reason, risk_level=risk_level)
        
        # --- Filter 2: Sinyal Kedaluwarsa ---
        if config.FILTER_OLD_SIGNALS_ENABLED:
            try:
                signal_time = datetime.fromisoformat(signal.get("timestamp"))
                age_minutes = (datetime.now(timezone.utc) - signal_time).total_seconds() / 60
                if age_minutes > config.SIGNAL_VALIDITY_MINUTES:
                    return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=f"Sinyal kedaluwarsa ({age_minutes:.1f} menit lalu).")
            except (TypeError, ValueError):
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Timestamp sinyal tidak valid.")

        # --- Filter 3 (BARU): Cek Riwayat Stop Loss ---
        if config.AVOID_BUYING_AFTER_SL:
            if self._check_for_recent_sl(coin_pair):
                reason = f"Pembelian dicegah karena Stop Loss terdeteksi dalam {config.SIGNAL_VALIDITY_MINUTES} menit terakhir."
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=reason)
        # --- AKHIR DARI FILTER BARU ---

        print(f"\n✅ Sinyal {coin_pair} (Risk: {signal.get('risk_level')}) valid & tidak kedaluwarsa. Melanjutkan ke analisis pasar...")
        print("--- Menganalisis Kondisi Pasar Global (BTC)... ---")
        
        btc_tf = getattr(config, 'BTC_FILTER_TIMEFRAME', '1h')
        btc_sma = getattr(config, 'BTC_FILTER_SMA_PERIOD', 50)
        
        btc_condition = self._analyze_asset_condition("BTCUSDT", btc_tf, btc_sma)

        if btc_condition["error"]:
            reason = btc_condition["error"]
            print(f"❌ Gagal Analisis Global: {reason}")
            return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=reason)
        
        if btc_condition.get("warning"):
            print(f"⚠️  Peringatan (BTC): {btc_condition['warning']}")

        market_status = "🟢 HIJAU (Aman)" if btc_condition["is_above_sma"] else "🟡 KUNING (Waspada/Netral)"
        print(f"Status Pasar Global: {market_status}")

        if market_status == "🟢 HIJAU (Aman)":
            print("Pasar AMAN. Menjalankan validasi kondisi harga...")
            return self._validate_price_conditions(signal)

        elif market_status == "🟡 KUNING (Waspada/Netral)":
            if config.ALTCOIN_TREND_FILTER_ENABLED:
                print(f"Pasar NETRAL. Melakukan pengecekan kedua pada {coin_pair} (filter altcoin aktif)...")
                alt_condition = self._analyze_asset_condition(coin_pair, btc_tf, btc_sma)
                if alt_condition["error"]:
                    reason = alt_condition["error"]
                    print(f"❌ Gagal Analisis Lokal untuk {coin_pair}: {reason}")
                    return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=reason)
                if alt_condition.get("warning"):
                    print(f"⚠️  Peringatan ({coin_pair}): {alt_condition['warning']}")
                if alt_condition["is_above_sma"]:
                    print(f"Tren lokal {coin_pair} KUAT. Menjalankan validasi kondisi harga...")
                    return self._validate_price_conditions(signal)
                else:
                    return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Pasar netral & tren lokal juga LEMAH.")
            else:
                reason = "Pasar netral & filter tren altcoin dimatikan. Trade tidak dilanjutkan."
                print(f"❌ {reason}")
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=reason)
        
        return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Kondisi pasar tidak terdefinisi.")