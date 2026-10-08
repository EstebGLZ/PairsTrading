from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True, slots=True)
class TradingConfig:
    entry_zscore: float = 2.0
    exit_zscore: float = 0.0
    stop_zscore: float = 3.5
    
class TradingSignal(Enum):
    LONG_SPREAD = 1
    HOLD = 0
    SHORT_SPREAD = -1
    EXIT = 2