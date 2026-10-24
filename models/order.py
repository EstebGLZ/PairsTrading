from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from models.pair import Pair


class TradingSignal(Enum):
    LONG_SPREAD = 1
    HOLD = 0
    SHORT_SPREAD = -1
    EXIT = 2


@dataclass(frozen=True, slots=True)
class TradingOrder:
    # Entry info
    pair: Pair
    signal: TradingSignal
    signal_date: datetime
    zscore: float
    # Stop loss info
    stop_loss_zscore: float | None = None
    time_exit: datetime | None = None
