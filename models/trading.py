from dataclasses import dataclass
from enum import Enum
from datetime import datetime

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
    
@dataclass
class PairPosition:
    ticker_y: str
    ticker_x: str

    direction: TradingSignal

    entry_date: datetime
    entry_zscore: float

    quantity_y: float
    quantity_x: float

    hedge_ratio: float
    
    entry_price_y: float
    entry_price_x: float

    exit_date: datetime | None = None
    exit_zscore: float | None = None

    exit_price_y: float | None = None
    exit_price_x: float | None = None
    
    @property
    def is_open(self) -> bool:
        return self.exit_date is None
    
    @property
    def pair(self) -> tuple[str, str]:
        return (self.ticker_y, self.ticker_x)
    
    