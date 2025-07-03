# Auto Trade Bot/binance/models.py
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

@dataclass
class TargetInfo:
    """Mewakili informasi target harga."""
    level: int
    price: float
    percentage_change: Optional[float] = None
    status: Optional[str] = None


@dataclass
class StopLossInfo:
    """Mewakili informasi stop-loss."""
    level: int
    price: float
    percentage_change: Optional[float] = None
    status: Optional[str] = None


@dataclass
class TradeDecision:
    """Mewakili keputusan trading berdasarkan sinyal."""
    decision: str  # "BUY", "SKIP", atau "FAIL"
    coin_pair: str
    reason: str
    current_price: Optional[float] = None
    entry_price: Optional[float] = None
    risk_level: Optional[str] = None # --- BARU: Menambahkan level risiko
    targets: List[TargetInfo] = field(default_factory=list)
    stop_losses: List[StopLossInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Mengonversi dataclass menjadi dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Mengonversi dataclass menjadi string JSON."""
        return json.dumps(self.to_dict(), indent=4)