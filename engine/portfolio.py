import logging
from datetime import datetime

from models import TradingOrder, Pair, PairPosition
from utils.validation_utils import ValidationUtils as VUtils

logger = logging.getLogger(__name__)


class Portfolio:
    """
    Class representing a trading porfolio. It handles the position and capital
    """

    def __init__(self, starting_capital: float = 10_000) -> None:
        VUtils.require_positive("starting_capital", starting_capital)

        self.starting_capital: float = starting_capital
        self.available_cash: float = starting_capital
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

        # Make sure we don't already have a position
        if self.get_position(*position.pair):
            logger.debug(f"Position rejected: position already opened.")
            return False

        # Make sure we don't spend more than we have
        if position.entry_gross_exposure > self.available_cash:
            logger.debug(
                f"Position rejected: insufficient balance {position.entry_gross_exposure} > {self.available_cash}")
            return False

        # Open the position
        self.open_positions[position.pair] = position
        self.available_cash -= position.entry_gross_exposure
        self.reserved_capital += position.entry_gross_exposure

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
        # Retrieve the position
        position: PairPosition | None = self.get_position(*pair.pair)

        # Make sure we have an opened position
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

        # Update portfolio
        self.open_positions.pop(position.pair)
        self.closed_positions.append(position)
        self.available_cash += position.entry_gross_exposure + position.realized_pnl
        self.reserved_capital -= position.entry_gross_exposure

        return True

    def close_all(self, exit_date: datetime, prices: dict[str, float]) -> None:
        """
        Close every position
        :param exit_date: The exit date
        :param prices: The prices at which the position was closed
        :raises ValueError: If one of the given number is not valid
        """
        for position in list(self.open_positions.values()):
            self.close_position(
                pair=position.pair_model,
                exit_date=exit_date,
                exit_zscore=None,
                exit_price_y=prices[position.pair_model.ticker_y],
                exit_price_x=prices[position.pair_model.ticker_x],
            )

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
