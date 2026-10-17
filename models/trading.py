from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from models.pair import PairResult
from utils.validation_utils import ValidationUtils as VUtils


@dataclass(frozen=True, slots=True)
class TradingConfig:
    entry_zscore: float = 2.5  # zscore to trigger an entry
    exit_zscore: float = 0.0  # zscore to trigger an exit
    stop_zscore_delta: float = 1.0  # zscore delta to trigger a stop loss (entry_zscore + stop_zscore_delta)
    half_life_time_exit_factor: float = 3.0  # Time exit factor based on half life value
    zscore_window: int = 30  # zscore calculation rolling window
    max_position: int = 10  # How many position to trade at once
    pairs_top_n: int = 5  # The best n pairs to select for trading
    allocation_per_pair: float = 0.1  # Allocation of the portfolio per pair

    def __post_init__(self):
        for name, value in (("entry_zscore", self.entry_zscore),
                            ("exit_zscore", self.exit_zscore),
                            ("stop_zscore_delta", self.stop_zscore_delta)):
            VUtils.require_finite(name, value)

        VUtils.require_positive("stop_zscore_delta", self.stop_zscore_delta)
        VUtils.require_positive("half_life_time_exit_factor", self.half_life_time_exit_factor)
        VUtils.require_positive("zscore_window", self.zscore_window)
        VUtils.require_positive("max_position", self.max_position)
        VUtils.require_positive("pairs_top_n", self.pairs_top_n)
        VUtils.require_positive("allocation_per_pair", self.allocation_per_pair)

        if not (0 <= self.exit_zscore < self.entry_zscore):
            raise ValueError("Expected 0 <= exit_zscore < entry_zscore.")

        if self.max_position <= 0:
            raise ValueError("Expected max_position > 0.")

        if self.zscore_window <= 0:
            raise ValueError("Expected zscore_window > 0.")

        if self.pairs_top_n <= 0:
            raise ValueError("Expected pairs_top_n > 0.")
        if self.allocation_per_pair > 1:
            raise ValueError("Expected allocation_per_pair must be between 0 and 1.")


class TradingSignal(Enum):
    LONG_SPREAD = 1
    HOLD = 0
    SHORT_SPREAD = -1
    EXIT = 2


@dataclass
class PairPosition:
    """
    Classe representing a trading position
    """
    pair_model: PairResult

    direction: TradingSignal

    entry_date: datetime
    entry_zscore: float

    # Signed quantities
    quantity_y: float
    quantity_x: float

    hedge_ratio: float

    entry_price_y: float
    entry_price_x: float

    # Hard stops
    stop_loss_zscore: float
    time_exit: datetime | None

    # Exit information
    exit_date: datetime | None = None
    exit_zscore: float | None = None

    exit_price_y: float | None = None
    exit_price_x: float | None = None

    def close(self, exit_date: datetime, exit_zscore: float | None, exit_price_y: float, exit_price_x: float) -> bool:
        """
        Marks the position as closed
        :param exit_date: When the position was closed
        :param exit_zscore: The z-score of the position at exit time. None if forced exit (Time based)
        :param exit_price_y: Asset y's exit price
        :param exit_price_x: Asset x's exit price
        :return: Whether the position is closed
        """
        if not self.is_open:
            return False

        if exit_date < self.entry_date or exit_price_x <= 0 or exit_price_y <= 0:
            return False

        self.exit_date = exit_date
        self.exit_zscore = exit_zscore
        self.exit_price_y = exit_price_y
        self.exit_price_x = exit_price_x

        return True

    @property
    def is_open(self) -> bool:
        """
        position status
        :return: True if the position is open, False otherwise
        """
        return self.exit_date is None

    @property
    def pair(self) -> tuple[str, str]:
        """
        Get the position's pair
        :return: Tuple with y and x ticker
        """
        return self.pair_model.pair

    @property
    def holding_duration(self) -> timedelta | None:
        """
        Calculate the holding duration
        :return: None if position still opened. Otherwise holding duration as a timedelta
        """
        if self.exit_date is None:
            return None
        return self.exit_date - self.entry_date

    @property
    def entry_gross_exposure(self) -> float:
        """
        Gross entry exposure (abs of the quantities * their entry prices)
        :return: The gross exposure as a float
        """
        return (
                abs(self.quantity_y) * self.entry_price_y
                + abs(self.quantity_x) * self.entry_price_x
        )

    @property
    def entry_x_exposure(self) -> float:
        """
        :return: The x asset's gross exposure (unsigned) as a float
        """
        return abs(self.entry_price_x * self.quantity_x)

    @property
    def entry_y_exposure(self) -> float:
        """
        :return: The y asset's gross exposure (unsigned) as a float
        """
        return abs(self.entry_price_y * self.quantity_y)

    @property
    def realized_pnl(self) -> float | None:
        """
        Calculate the realized pnl
        :return: The realized pnl as a float or none if position still opened
        """
        if self.is_open:
            return None

        return (
                self.quantity_y * (self.exit_price_y - self.entry_price_y)
                + self.quantity_x * (self.exit_price_x - self.entry_price_x)
        )

    @property
    def realized_return(self) -> float | None:
        """
        Calculate realized return
        :return: The realized return as a float or none if position still opened
        """
        if self.is_open:
            return None

        return self.realized_pnl / self.entry_gross_exposure

    def unrealized_pnl(self, price_y: float, price_x: float) -> float | None:
        """
        Calculate the unrealized pnl
        :param price_y: The y asset's current price
        :param price_x: The x asset's current price
        :return: The unrealized pnl as a float or none if position still opened
        """
        if not self.is_open:
            raise ValueError("Cannot calculate unrealized PnL for a closed position.")

        return (
                self.quantity_y * (price_y - self.entry_price_y)
                + self.quantity_x * (price_x - self.entry_price_x)
        )


@dataclass(frozen=True, slots=True)
class TradingOrder:
    # Entry info
    pair: PairResult
    signal: TradingSignal
    signal_date: datetime
    zscore: float
    # Stop loss info
    stop_loss_zscore: float | None = None
    time_exit: datetime | None = None
