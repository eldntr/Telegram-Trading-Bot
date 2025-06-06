from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any, Dict
from datetime import datetime
import json

@dataclass
class BaseMessage:
    """Base class for all message types."""
    raw_text: str
    timestamp: datetime
    sender_id: Optional[int] = None
    message_id: Optional[int] = None

    def to_dict(self):
        """Converts the dataclass to a dictionary, handling datetime."""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d

@dataclass
class TargetInfo:
    level: int
    price: float
    percentage_change: Optional[float] = None
    status: Optional[str] = None

@dataclass
class StopLossInfo:
    level: int
    price: float
    percentage_change: Optional[float] = None
    status: Optional[str] = None

@dataclass
class SignalUpdate(BaseMessage):
    """Represents an update to an existing signal."""
    coin_pair: str = ""
    targets_hit: List[TargetInfo] = field(default_factory=list)
    stop_losses_triggered: List[StopLossInfo] = field(default_factory=list)
    update_type: str = ""
    message_type: str = "SignalUpdate"

@dataclass
class NewSignal(BaseMessage):
    """Represents a new trading signal."""
    coin_pair: str = ""
    risk_rank: Optional[str] = None
    risk_level: Optional[str] = None
    entry_price: Optional[float] = None
    targets: List[TargetInfo] = field(default_factory=list)
    stop_losses: List[StopLossInfo] = field(default_factory=list)
    social_media_link: Optional[str] = None
    data_analysis_link: Optional[str] = None
    message_type: str = "NewSignal"

@dataclass
class MarketAlert(BaseMessage):
    """Represents a market alert message."""
    coin: str = ""
    price_change_percentage: float = 0.0
    timeframe_minutes: int = 0
    alert_message: str = ""
    message_type: str = "MarketAlert"

@dataclass
class UnstructuredMessage(BaseMessage):
    """Represents a message that does not fit other models."""
    content: str = ""
    original_sender: Optional[str] = None
    message_type: str = "UnstructuredMessage"

    def __post_init__(self):
        if not self.content:
            self.content = self.raw_text

@dataclass
class DailyRecap(BaseMessage):
    """Represents a daily summary of trading signals."""
    date_range: Optional[str] = None
    targets_hit: Dict[str, List[str]] = field(default_factory=dict)
    running_signals: List[str] = field(default_factory=list)
    stop_losses_hit: List[str] = field(default_factory=list)
    total_signals: Optional[int] = None
    total_take_profits: Optional[int] = None
    total_stop_losses: Optional[int] = None
    message_type: str = "DailyRecap"