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
        - BUY: Sinyal valid dan harga di bawah entry price.
        - SKIP: Harga di atas entry price.
        - FAIL: Sinyal sudah tidak valid atau data kurang.
        """
        coin_pair = signal.get("coin_pair")
        entry_price = signal.get("entry_price")
        risk_level = signal.get("risk_level") # Ambil risk level dari sinyal

        if not coin_pair or entry_price is None:
            return TradeDecision(decision="FAIL", coin_pair=coin_pair or "N/A", reason="Sinyal tidak valid: 'coin_pair' atau 'entry_price' tidak ditemukan.", risk_level=risk_level)

        current_price = self.client.get_current_price(coin_pair)
        if current_price is None:
            return TradeDecision(decision="FAIL", coin_pair=coin_pair, entry_price=entry_price, reason=f"Gagal mendapatkan harga terkini untuk {coin_pair}.", risk_level=risk_level)

        # --- LOGIKA BARU: Validasi Sinyal Terhadap Harga Terkini ---
        try:
            stop_loss_price = signal['stop_losses'][0]['price']
            if current_price < stop_loss_price:
                reason = f"Harga saat ini ({current_price}) sudah di bawah level Stop Loss 1 ({stop_loss_price}). Sinyal dibatalkan untuk keamanan."
                return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason=reason, current_price=current_price, entry_price=entry_price, risk_level=risk_level)
        except (IndexError, KeyError, TypeError):
            return TradeDecision(decision="FAIL", coin_pair=coin_pair, reason="Sinyal tidak memiliki data Stop Loss (SL1) yang valid untuk divalidasi.", current_price=current_price, risk_level=risk_level)
        # --- AKHIR LOGIKA BARU ---
        
        # Logika lama: Beli jika harga saat ini lebih rendah atau sama dengan harga masuk.
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
                stop_losses=stop_losses,
                risk_level=risk_level # --- BARU: Teruskan risk_level
            )
        else:
            return TradeDecision(
                decision="SKIP",
                coin_pair=coin_pair,
                reason=f"Harga saat ini ({current_price}) lebih mahal dari harga masuk ({entry_price}).",
                current_price=current_price,
                entry_price=entry_price,
                risk_level=risk_level # --- BARU: Teruskan risk_level
            )