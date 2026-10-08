from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

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
    
    def close(self, exit_date:datetime, exit_zscore: float, exit_price_y:float, exit_price_x: float) -> None:
        if not self.is_open:
            return
        
        self.exit_date = exit_date
        self.exit_zscore = exit_zscore
        self.exit_price_y = exit_price_y
        self.exit_price_x = exit_price_x
    
    @property
    def is_open(self) -> bool:
        return self.exit_date is None
        
    @property
    def pair(self) -> tuple[str, str]:
        return (self.ticker_y, self.ticker_x)
    
    @property
    def holding_duration(self) -> timedelta | None:
        if self.exit_date is None:
            return None

        return (self.exit_date - self.entry_date)
    
    @property
    def entry_value(self) -> float:
        return (
            self.quantity_x * self.entry_price_x
            + self.quantity_y * self.entry_price_y
        )
    
     @property
    def exit_value(self) -> float | None:
        if self.is_open:
            return None
    
        return (
            self.quantity_x * self.exit_price_x
            + self.quantity_y * self.exit_price_y
        )
    
    
    