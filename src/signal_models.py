# signal_models.py
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from datetime import datetime

@dataclass
class BaseMessage:
    raw_text: str
    timestamp: datetime
    sender_id: Optional[int] = None
    message_id: Optional[int] = None
    message_type: str = field(init=False)

@dataclass
class TargetInfo:
    level: int
    price: float
    percentage_change: Optional[float] = None # Untuk NewSignal
    status: Optional[str] = None # HIT, PENDING (Untuk SignalUpdate)

@dataclass
class StopLossInfo:
    level: int
    price: float
    percentage_change: Optional[float] = None # Untuk NewSignal
    status: Optional[str] = None # TRIGGERED, PENDING (Untuk SignalUpdate)

@dataclass
class SignalUpdate(BaseMessage):
    coin_pair: str = ""  # Added default value
    targets_hit: List[TargetInfo] = field(default_factory=list)
    stop_losses_triggered: List[StopLossInfo] = field(default_factory=list)
    update_type: str = "" # "TARGET_HIT" atau "STOP_LOSS_TRIGGERED"

    def __post_init__(self):
        self.message_type = "SignalUpdate"

@dataclass
class NewSignal(BaseMessage):
    coin_pair: str = ""  # Added default value
    risk_rank: Optional[str] = None # Misal "392th/462"
    risk_level: Optional[str] = None # Misal "High"
    entry_price: Optional[float] = None
    targets: List[TargetInfo] = field(default_factory=list)
    stop_losses: List[StopLossInfo] = field(default_factory=list)
    social_media_link: Optional[str] = None
    data_analysis_link: Optional[str] = None

    def __post_init__(self):
        self.message_type = "NewSignal"

@dataclass
class MarketAlert(BaseMessage):
    coin: str = ""  # Added default value
    price_change_percentage: float = 0.0  # Added default value
    timeframe_minutes: int = 0  # Added default value
    alert_message: str = ""  # Added default value

    def __post_init__(self):
        self.message_type = "MarketAlert"

@dataclass
class UnstructuredMessage(BaseMessage):
    original_sender: Optional[str] = None # Jika ada info pengirim/sumber
    content: str = ""

    def __post_init__(self):
        self.message_type = "UnstructuredMessage"
        if not self.content: # Jika content tidak diisi eksplisit, ambil dari raw_text
            self.content = self.raw_text