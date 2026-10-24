from dataclasses import dataclass
from datetime import datetime, timedelta

from models.order import TradingSignal
from models.pair import Pair
from utils.validation_utils import ValidationUtils as VUtils


@dataclass
class PairPosition:
    """
    Classe representing a trading position
    """
    pair_model: Pair

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

        if exit_date < self.entry_date:
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

    def __post_init__(self) -> None:
        VUtils.require_positive("entry_price_y", self.entry_price_y)
        VUtils.require_positive("entry_price_x", self.entry_price_x)
        VUtils.require_finite("quantity_y", self.quantity_y)
        VUtils.require_finite("quantity_x", self.quantity_x)
        if self.quantity_y == 0 and self.quantity_x == 0:
            raise ValueError("Position quantities cannot both be zero.")
