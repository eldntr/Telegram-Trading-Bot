# Auto Trade Bot/binance/strategy.py
from typing import Dict, Any, Optional
from datetime import datetime, timezone
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

    ### DIPERBARUI dengan Logika Dinamis ###
    def _analyze_asset_condition(self, symbol: str, interval: str, sma_period: int) -> Dict[str, Any]:
        """
        Menganalisis kondisi sebuah aset. Jika data terbatas (untuk koin baru),
        maka akan menggunakan parameter analisis yang dinamis.
        """
        data_to_request = sma_period + 1
        klines = self.client.get_klines(symbol=symbol, interval=interval, limit=data_to_request)
        
        candles_received = len(klines) if klines else 0
        MINIMUM_CANDLES_FOR_ANALYSIS = 15  # Batas minimum data untuk bisa dianalisis

        if candles_received < MINIMUM_CANDLES_FOR_ANALYSIS:
            return {"error": f"Data sangat minim ({candles_received} lilin), analisis dibatalkan."}

        # Jika data terbatas, gunakan parameter dinamis. Jika tidak, gunakan parameter standar.
        effective_sma_period = min(sma_period, candles_received)
        warning_message = None
        if candles_received < data_to_request:
            warning_message = f"Data terbatas ({candles_received} lilin), SMA dihitung menggunakan periode {effective_sma_period}."

        close_prices = [float(k[4]) for k in klines]
        # Gunakan periode efektif untuk kalkulasi
        is_above_sma = close_prices[-1] >= np.mean(close_prices[-effective_sma_period:])

        return {"is_above_sma": is_above_sma, "warning": warning_message, "error": None}

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
        ### LANGKAH 1: Validasi Awal Sinyal (Fail-Fast) ###
        coin_pair = signal.get("coin_pair")
        if not coin_pair:
            return TradeDecision(decision="FAIL", reason="Sinyal tidak memiliki 'coin_pair'.")

        if config.FILTER_OLD_SIGNALS_ENABLED:
            try:
                signal_time = datetime.fromisoformat(signal.get("timestamp"))
                age_minutes = (datetime.now(timezone.utc) - signal_time).total_seconds() / 60
                if age_minutes > config.SIGNAL_VALIDITY_MINUTES:
                    return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=f"Sinyal kedaluwarsa ({age_minutes:.1f} menit lalu).")
            except (TypeError, ValueError):
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Timestamp sinyal tidak valid.")

        ### LANGKAH 2: Gerbang Utama - Analisis Kondisi Pasar ###
        print(f"\n✅ Sinyal {coin_pair} valid & tidak kedaluwarsa. Melanjutkan ke analisis pasar...")
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

        ### LANGKAH 3: Pengecekan Detail Berdasarkan Status Pasar ###
        if market_status == "🟢 HIJAU (Aman)":
            print("Pasar AMAN. Menjalankan validasi kondisi harga...")
            return self._validate_price_conditions(signal)

        elif market_status == "🟡 KUNING (Waspada/Netral)":
            print(f"Pasar NETRAL. Melakukan pengecekan kedua pada {coin_pair}...")
            
            alt_condition = self._analyze_asset_condition(coin_pair, btc_tf, btc_sma)

            if alt_condition["error"]:
                reason = alt_condition["error"]
                print(f"❌ Gagal Analisis Lokal untuk {coin_pair}: {reason}")
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=reason)

            ### BARU: Menampilkan Peringatan Jika Ada ###
            if alt_condition.get("warning"):
                print(f"⚠️  Peringatan ({coin_pair}): {alt_condition['warning']}")

            if alt_condition["is_above_sma"]:
                print(f"Tren lokal {coin_pair} KUAT (berdasarkan data yang tersedia). Menjalankan validasi kondisi harga...")
                return self._validate_price_conditions(signal)
            else:
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Pasar netral & tren lokal juga LEMAH.")
        
        return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Kondisi pasar tidak terdefinisi.")