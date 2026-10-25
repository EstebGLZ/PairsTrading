from dataclasses import dataclass
from datetime import datetime, timedelta

from models.order import TradingSignal
from models.pair import Pair
from utils.validation_utils import ValidationUtils as VUtils


@dataclass
class PairPosition:
    """
    Represents a statistical arbitrage pair trading position.

    Tracks quantities, entry/exit prices, risk parameters, transaction costs,
    and calculates gross and net performance metrics.
    """
    pair_model: Pair
    direction: TradingSignal

    entry_date: datetime
    entry_zscore: float

    # Signed trade quantities (positive = Long, negative = Short)
    quantity_y: float
    quantity_x: float

    hedge_ratio: float

    entry_price_y: float
    entry_price_x: float

    # Risk management triggers
    stop_loss_zscore: float
    time_exit: datetime | None

    # Exit details (populated upon closure)
    exit_date: datetime | None = None
    exit_zscore: float | None = None
    exit_price_y: float | None = None
    exit_price_x: float | None = None

    # Transaction costs & frictions
    total_commission: float = 0.0
    total_slippage: float = 0.0
    borrow_fees: float = 0.0

    def __post_init__(self) -> None:
        """Validate position invariants upon creation."""
        VUtils.require_positive("entry_price_y", self.entry_price_y)
        VUtils.require_positive("entry_price_x", self.entry_price_x)
        VUtils.require_finite("quantity_y", self.quantity_y)
        VUtils.require_finite("quantity_x", self.quantity_x)
        if self.quantity_y == 0 and self.quantity_x == 0:
            raise ValueError("Position quantities cannot both be zero.")

    @property
    def is_open(self) -> bool:
        """Return True if the position is currently open."""
        return self.exit_date is None

    @property
    def pair(self) -> tuple[str, str]:
        """Return the (ticker_y, ticker_x) tuple."""
        return self.pair_model.pair

    @property
    def holding_duration(self) -> timedelta | None:
        """Return the holding duration as a timedelta, or None if still open."""
        if self.exit_date is None:
            return None
        return self.exit_date - self.entry_date

    @property
    def entry_gross_exposure(self) -> float:
        """Total absolute dollar capital deployed across both legs (|Qy|*Py + |Qx|*Px)."""
        return abs(self.quantity_y) * self.entry_price_y + abs(self.quantity_x) * self.entry_price_x

    @property
    def entry_y_exposure(self) -> float:
        """Absolute dollar exposure of the Y leg (|Qy| * Py)."""
        return abs(self.quantity_y) * self.entry_price_y

    @property
    def entry_x_exposure(self) -> float:
        """Absolute dollar exposure of the X leg (|Qx| * Px)."""
        return abs(self.quantity_x) * self.entry_price_x

    @property
    def total_cost(self) -> float:
        """Total transaction friction (commissions + slippage + borrow fees)."""
        return self.total_commission + self.total_slippage + self.borrow_fees

    @property
    def gross_pnl(self) -> float | None:
        """Raw PnL based purely on price movements without costs, or None if open."""
        if self.is_open:
            return None
        return (
                self.quantity_y * (self.exit_price_y - self.entry_price_y)
                + self.quantity_x * (self.exit_price_x - self.entry_price_x)
        )

    @property
    def realized_pnl(self) -> float | None:
        """Net realized PnL after deducting all transaction costs, or None if open."""
        if self.is_open:
            return None
        return self.gross_pnl - self.total_cost

    @property
    def realized_return(self) -> float | None:
        """Net percentage return relative to gross entry exposure, or None if open."""
        if self.is_open:
            return None
        return self.realized_pnl / self.entry_gross_exposure

    def unrealized_pnl(self, price_y: float, price_x: float) -> float:
        """
        Calculate mark-to-market gross unrealized PnL based on current prices.

        :param price_y: Current price of asset Y.
        :param price_x: Current price of asset X.
        :return: Unrealized gross PnL.
        :raises ValueError: If the position is already closed.
        """
        if not self.is_open:
            raise ValueError("Cannot calculate unrealized PnL for a closed position.")

        return (
                self.quantity_y * (price_y - self.entry_price_y)
                + self.quantity_x * (price_x - self.entry_price_x)
        )

    def close(
            self,
            exit_date: datetime,
            exit_zscore: float | None,
            exit_price_y: float,
            exit_price_x: float,
    ) -> bool:
        """
        Mark the position as closed and record exit execution parameters.

        :param exit_date: Timestamp of closure.
        :param exit_zscore: Spread z-score at exit, or None if time-based / forced exit.
        :param exit_price_y: Execution exit price for asset Y.
        :param exit_price_x: Execution exit price for asset X.
        :return: True if successfully closed, False if already closed or invalid date.
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
