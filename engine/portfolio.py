import logging
from datetime import datetime

from models import TradingOrder, Pair, PairPosition, BacktestConfig
from utils.validation_utils import ValidationUtils as VUtils

logger = logging.getLogger(__name__)


class Portfolio:
    """
    Class representing a trading porfolio. It handles the position and capital
    """

    def __init__(self, config: BacktestConfig) -> None:
        self.starting_capital: int = config.starting_capital
        self.commission_pct: float = config.commission_pct
        self.slippage_pct: float = config.slippage_pct
        self.borrow_rate: float = config.borrow_rate
        self.available_cash: float = self.starting_capital
        self.reserved_capital: float = 0.0
        self.open_positions: dict[tuple[str, str], PairPosition] = dict()
        self.closed_positions: list[PairPosition] = []
        self.equity: dict[datetime, float] = dict()

    def get_position(self, ticker_y: str, ticker_x: str) -> PairPosition | None:
        """
        Get a position based on the tickers.
        :param ticker_y: The y asset's ticker
        :param ticker_x: The x asset's ticker
        :return: The found position or None if position not found.
        """
        return self.open_positions.get((ticker_y, ticker_x), None)

    def has_position(self, ticker) -> bool:
        """
        Check if a ticker is currently traded.
        :param ticker: The ticker to look for
        :return: Whether the ticker is currently in a position or not
        """
        return any(ticker in pair for pair in self.open_positions.keys())

    def open_position(self,
                      order: TradingOrder,
                      entry_date: datetime,
                      quantity_y: float,
                      quantity_x: float,
                      entry_price_y: float,
                      entry_price_x: float) -> bool:
        """
        Open a position
        :param order: The order regarding the position
        :param entry_date: When the position was opened
        :param quantity_y: The amount of y to long/short
        :param quantity_x: The amount of x to long/short
        :param entry_price_y: Y asset's entry price
        :param entry_price_x: X asset's entry price
        :return: Whether the position was opened or not
        :raises ValueError: If one of the given number is not valid
        """

        # Make sure we don't already have a position
        if self.get_position(*order.pair.pair):
            logger.debug(f"Position rejected: position already opened.")
            return False

        position: PairPosition = PairPosition(
            pair_model=order.pair,
            direction=order.signal,
            entry_date=entry_date,
            entry_zscore=order.zscore,
            quantity_y=quantity_y,
            quantity_x=quantity_x,
            hedge_ratio=order.pair.hedge_ratio,
            entry_price_y=entry_price_y,
            entry_price_x=entry_price_x,
            stop_loss_zscore=order.stop_loss_zscore,
            time_exit=order.time_exit
        )

        # Calculate the fees
        entry_commission: float = position.entry_gross_exposure * self.commission_pct
        entry_slippage: float = position.entry_gross_exposure * self.slippage_pct
        total_entry_outflow: float = position.entry_gross_exposure + entry_commission + entry_slippage

        # Make sure we don't spend more than we have
        if total_entry_outflow > self.available_cash:
            logger.debug(f"Position rejected: insufficient cash {total_entry_outflow} > {self.available_cash}")
            return False

        position.total_commission = entry_commission
        position.total_slippage = entry_slippage

        # Open the position
        self.open_positions[position.pair] = position
        self.available_cash -= total_entry_outflow
        self.reserved_capital += position.entry_gross_exposure

        # Logging
        logger.info(
            f"🟢 OPEN  | {entry_date.strftime('%Y-%m-%d')} | "
            f"{position.pair_model.ticker_y}/{position.pair_model.ticker_x} | "
            f"{position.direction.name:<12} | Z: {position.entry_zscore:+.2f} | "
            f"Alloc: ${position.entry_gross_exposure:,.2f} | "
            f"Cash: ${self.available_cash:,.2f}"
        )
        return True

    def close_position(self, pair: Pair, exit_date: datetime, exit_zscore: float | None,
                       exit_price_y: float,
                       exit_price_x: float) -> bool:
        """
        Close a position
        :param pair: The pair to trade
        :param exit_date: Closing date
        :param exit_zscore: The zscore which gave closing signal
        :param exit_price_y: Y asset's exit price
        :param exit_price_x: X asset's exit price
        :return: Whether the position was closed or not
        """
        position: PairPosition | None = self.get_position(*pair.pair)
        if position is None or not position.is_open:
            logger.debug(f"Position close rejected: position either not found or already closed.")
            return False

        # Make sure the given numbers are usable
        if exit_zscore is not None:
            VUtils.require_finite("zscore", exit_zscore)

        for name, value in (("exit_price_x", exit_price_x), ("exit_price_y", exit_price_y)):
            VUtils.require_positive(name, value)

        # Close the position
        closed: bool = position.close(
            exit_date=exit_date,
            exit_zscore=exit_zscore,
            exit_price_y=exit_price_y,
            exit_price_x=exit_price_x)

        if not closed:
            logger.error(f"Could not close position: {position}")
            return False

        # Calculate exit fees
        exit_gross_exposure: float = abs(position.quantity_y) * exit_price_y + abs(position.quantity_x) * exit_price_x
        exit_commission: float = exit_gross_exposure * self.commission_pct
        exit_slippage: float = exit_gross_exposure * self.slippage_pct

        # Calculate borrow fees
        short_exposure = 0.0
        if position.quantity_y < 0:
            short_exposure += abs(position.quantity_y) * position.entry_price_y
        if position.quantity_x < 0:
            short_exposure += abs(position.quantity_x) * position.entry_price_x

        duration_days = position.holding_duration.days if position.holding_duration else 0
        borrow_fees: float = short_exposure * self.borrow_rate * (duration_days / 360.0)

        position.total_commission += exit_commission
        position.total_slippage += exit_slippage
        position.borrow_fees = borrow_fees

        # Update portfolio
        self.open_positions.pop(position.pair)
        self.closed_positions.append(position)
        self.reserved_capital -= position.entry_gross_exposure
        self.available_cash += (
                position.entry_gross_exposure
                + position.gross_pnl
                - exit_commission
                - exit_slippage
                - borrow_fees
        )

        # Logging
        tag = "🛑 STOP " if (
                exit_zscore is not None and abs(exit_zscore) >= abs(position.stop_loss_zscore)) else "🔴 CLOSE"
        z_str = f"{exit_zscore:+.2f}" if exit_zscore is not None else "TIME"
        days_str = f"{position.holding_duration.days}d" if position.holding_duration else "0d"

        logger.info(
            f"{tag} | {exit_date.strftime('%Y-%m-%d')} | "
            f"{position.pair_model.ticker_y}/{position.pair_model.ticker_x} | "
            f"Exit Z: {z_str} | Held: {days_str} | "
            f"Net PnL: {position.realized_pnl:+,.2f}$ ({position.realized_return:+.2%}) | "
            f"Fees: ${position.total_cost:.2f}"
        )
        return True

    def update_equity(self, date: datetime, prices: dict[str, float], ) -> None:
        """
        Update the portfolio's equity. This method must be called at the end of each day or each candle
        :param date: Which date the equity represents
        :param prices: What are the currents assets' prices
        """
        for position in self.open_positions.values():
            for ticker in position.pair:
                VUtils.require_positive(
                    f"valuation_price[{ticker}]",
                    prices[ticker],
                )

        unrealized_pnl: float = sum(
            position.unrealized_pnl(
                price_y=prices[position.pair_model.ticker_y],
                price_x=prices[position.pair_model.ticker_x],
            )
            for position in self.open_positions.values()
        )
        new_equity: float = self.available_cash + self.reserved_capital + unrealized_pnl
        VUtils.require_finite("equity", new_equity)
        self.equity[date] = new_equity

    def __str__(self) -> str:
        realized_pnl: float = sum(p.realized_pnl for p in self.closed_positions)
        latest_equity = next(reversed(self.equity.values()), self.starting_capital)
        unrealized_pnl = latest_equity - self.available_cash - self.reserved_capital
        total_return = latest_equity / self.starting_capital - 1

        return (f"Starting capital: {self.starting_capital}\n"
                f"Current available capital: {self.available_cash}\n"
                f"Reserved capital: {self.reserved_capital}\n"
                f"Unrealized pnl: {unrealized_pnl}\n"
                f"Total return: {total_return}\n"
                f"Realized pnl: {realized_pnl}\n"
                f"Opened position: {len(self.open_positions)}\n"
                f"Closed position: {len(self.closed_positions)}"
                )
