import logging
from datetime import datetime

import pandas as pd

from data.columns import Column
from data.feature import FeatureEngine
from data.fetcher import DataFetcher
from engine.pair_engine import PairEngine
from engine.portfolio import Portfolio
from engine.trading_engine import TradingEngine
from models import PairSelectionConfig, TradingConfig, TradingOrder, TradingSignal, Pair, PairPosition, BacktestConfig

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Class used to backtest pair trading strategy
    """

    def __init__(self, stocks: list[str], start_date: datetime, end_date: datetime, config: BacktestConfig):
        """
        Constructor
        :param stocks: The stocks to trade
        :param start_date: When the backtest starts
        :param end_date: When the backtest ends
        :param config: The backtest configuration
        """
        self.data: pd.DataFrame = DataFetcher.fetch(stocks, start_date, end_date)
        self.portfolio: Portfolio = Portfolio(config)
        self.pending_orders: list[TradingOrder] = []
        self._started: bool = False
        self.config: BacktestConfig = config

    def start(self, pair_config: PairSelectionConfig, trading_config: TradingConfig) -> None:
        """
        Start the backtest
        :param pair_config: The configuration used to select the pairs
        :param trading_config: The trading configuration
        :raises: ValueError in case of invalid number or trading signals in the backtest
        """
        logger.info("Starting backtest...")

        # No duplicate execution
        if self._started:
            raise RuntimeError("Backtest already started")

        self._started = True

        FeatureEngine.add_features(self.data)
        dates = (
            self.data.index
            .get_level_values("Date")
            .unique()
            .sort_values()
        )

        if len(dates) <= self.config.formation_window:
            raise ValueError("Not enough sessions for formation and at least one trading session.")

        close_matrix = self.data[Column.CLOSE].unstack(level="Ticker")
        open_matrix = self.data[Column.OPEN].unstack(level="Ticker")

        # Handle the formation windows
        for i in range(0, len(dates) - self.config.formation_window, self.config.trading_window):
            # Get the current trading dates
            formation_dates = dates[i:i + self.config.formation_window]
            trading_dates = dates[
                i + self.config.formation_window:
                i + self.config.formation_window + self.config.trading_window
            ]

            # Generate pairs for this session
            formation_data = self.data[self.data.index.get_level_values("Date").isin(formation_dates)]
            pairs: list[Pair] = PairEngine.select_pairs(data=formation_data, config=pair_config)
            pairs = PairEngine.rank_pairs(pairs=pairs, top_n=trading_config.pairs_top_n)

            # Go through each trading dates
            for j, date in enumerate(trading_dates):
                # Get today's prices
                opening_prices = open_matrix.loc[date].to_dict()
                closing_prices = close_matrix.loc[date].to_dict()
                # Execute orders
                self._execute_pending_orders(date, opening_prices, trading_config)

                current_idx = i + self.config.formation_window + j
                start_idx = max(0, current_idx - trading_config.zscore_window + 1)
                end_idx = current_idx + 1
                hist_close = close_matrix.iloc[start_idx:end_idx]

                # Handle exits
                for pos_key, position in list(self.portfolio.open_positions.items()):
                    try:
                        # Get the pair's price
                        prices = {
                            position.pair_model.ticker_y: hist_close[position.pair_model.ticker_y].tolist(),
                            position.pair_model.ticker_x: hist_close[position.pair_model.ticker_x].tolist(),
                        }

                        curr_position: PairPosition | None = self.portfolio.get_position(*position.pair)
                        order: TradingOrder | None = TradingEngine.process_pair(
                            pair=curr_position.pair_model,
                            prices=prices,
                            date=date,
                            position=curr_position,
                            config=trading_config
                        )

                        # Schedule exit order
                        if order is not None:
                            self.pending_orders.append(order)

                    except Exception:
                        logging.exception("Could not process pair %s/%s", *position.pair)
                        raise

                # Check for entries across selected pairs
                for pair in pairs:
                    # Don't trade more than what is allowed
                    if len(self.portfolio.open_positions) >= trading_config.max_position:
                        break

                    # Don't trade a ticker more than once
                    if self.portfolio.has_position(pair.ticker_x) or self.portfolio.has_position(pair.ticker_y):
                        continue

                    try:
                        # Get the prices
                        prices = {
                            pair.ticker_y: hist_close[pair.ticker_y].tolist(),
                            pair.ticker_x: hist_close[pair.ticker_x].tolist(),
                        }
                        order: TradingOrder | None = TradingEngine.process_pair(
                            pair=pair,
                            prices=prices,
                            date=date,
                            position=None,
                            config=trading_config
                        )

                        # Schedule the order
                        if order is not None:
                            self.pending_orders.append(order)

                    except Exception:
                        logging.exception("Could not process pair %s/%s", *pair.pair)
                        raise

                # End of day equity update
                self.portfolio.update_equity(date, closing_prices)

        # Backtest done
        logger.info("Finished backtest")
        logger.info(f"Orders that have not been executed: {len(self.pending_orders)}")
        self.pending_orders.clear()

    def _execute_pending_orders(self, date: datetime, prices: dict[str, float], config: TradingConfig) -> None:
        """
        Execute all the pending orders
        :param date: The trading date
        :param prices: The assets' prices
        :param config: The trading config
        :return: None
        """

        # Sort by exit first so that they are executed first
        orders = sorted(
            self.pending_orders,
            key=lambda order: order.signal != TradingSignal.EXIT,
        )

        self.pending_orders.clear()  # Clear the list as we handle each order

        # Iterate through each order
        for order in orders:
            # Get the pair's current info
            pair: Pair = order.pair
            price_y: float = prices[pair.ticker_y]
            price_x: float = prices[pair.ticker_x]

            # Open a position
            if order.signal in (TradingSignal.LONG_SPREAD, TradingSignal.SHORT_SPREAD):
                # Make sure we don't trade a ticker more than once
                if self.portfolio.has_position(pair.ticker_x) or self.portfolio.has_position(pair.ticker_y):
                    continue
                try:
                    current_equity = next(reversed(self.portfolio.equity.values()), self.portfolio.starting_capital)
                    target_capital = config.allocation_per_pair * current_equity
                    capital_to_allocate = min(target_capital, self.portfolio.available_cash)

                    # No negative capital
                    if capital_to_allocate <= 0:
                        logger.debug("Pas assez de liquidités disponibles pour ouvrir la position.")
                        continue

                    quantity_y, quantity_x = TradingEngine.calculate_position_sizing(
                        capital=capital_to_allocate,
                        price_x=price_x,
                        price_y=price_y,
                        hedge_ratio=pair.hedge_ratio,
                        direction=order.signal
                    )

                    self.portfolio.open_position(
                        order=order,
                        entry_date=date,
                        quantity_y=quantity_y,
                        quantity_x=quantity_x,
                        entry_price_y=price_y,
                        entry_price_x=price_x,
                    )
                except ValueError as e:
                    logging.exception(f"Error when opening position: {e}")

            elif order.signal == TradingSignal.EXIT:  # Close the position
                self.portfolio.close_position(
                    pair=pair,
                    exit_date=date,
                    exit_zscore=order.zscore,
                    exit_price_x=price_x,
                    exit_price_y=price_y)
            else:
                raise ValueError(f"Unexpected order signal: {order.signal}")
