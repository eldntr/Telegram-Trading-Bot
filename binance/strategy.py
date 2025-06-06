# Auto Trade Bot/binance/strategy.py
from typing import Dict, Any
from .client import BinanceClient
from .models import TradeDecision, TargetInfo, StopLossInfo

class TradingStrategy:
    """
    Mengevaluasi sinyal trading dan membuat keputusan berdasarkan strategi.
    """
    def __init__(self, binance_client: BinanceClient):
        self.client = binance_client

    def evaluate_new_signal(self, signal: Dict[str, Any]) -> TradeDecision:
        """
        Mengevaluasi sinyal baru dan memutuskan apakah akan membeli.
        - BUY: Harga saat ini <= harga masuk.
        - SKIP: Harga saat ini > harga masuk.
        - FAIL: Gagal mendapatkan harga (koin mungkin tidak ada di Binance).

        Args:
            signal: Sebuah dictionary yang mewakili sinyal baru dari file new_signals.json.

        Returns:
            Objek TradeDecision yang berisi keputusan dan data terkait.
        """
        coin_pair = signal.get("coin_pair")
        entry_price = signal.get("entry_price")

        if not coin_pair or entry_price is None:
            return TradeDecision(
                decision="FAIL",
                coin_pair=coin_pair or "N/A",
                reason="Sinyal tidak valid: 'coin_pair' atau 'entry_price' tidak ditemukan."
            )

        current_price = self.client.get_current_price(coin_pair)

        if current_price is None:
            return TradeDecision(
                decision="FAIL",
                coin_pair=coin_pair,
                entry_price=entry_price,
                reason=f"Gagal mendapatkan harga terkini untuk {coin_pair}. Koin kemungkinan tidak ada di Binance."
            )

        # Logika keputusan
        if current_price <= entry_price:
            targets = [TargetInfo(**t) for t in signal.get("targets", [])]
            stop_losses = [StopLossInfo(**sl) for sl in signal.get("stop_losses", [])]
            
            return TradeDecision(
                decision="BUY",
                coin_pair=coin_pair,
                reason=f"Harga saat ini ({current_price}) lebih rendah dari atau sama dengan harga masuk ({entry_price}).",
                current_price=current_price,
                entry_price=entry_price,
                targets=targets,
                stop_losses=stop_losses
            )
        else:
            return TradeDecision(
                decision="SKIP",
                coin_pair=coin_pair,
                reason=f"Harga saat ini ({current_price}) lebih mahal dari harga masuk ({entry_price}).",
                current_price=current_price,
                entry_price=entry_price
            )