import logging
from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np

from models import TradingConfig, TradingSignal, TradingOrder, Pair, PairPosition
from utils.validation_utils import ValidationUtils as VUtils

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Trading engine handling position related calculation such as sizing, and signals
    """

    @staticmethod
    def _generate_entry_signal(zscore: float,
                               pair: Pair,
                               config: TradingConfig,
                               date: datetime) -> TradingOrder | None:
        """
        Check for an entry signal
        :param zscore: The current zscore
        :param pair: The traded pair
        :param config: The trading configuration
        :param date: The traded date
        :return: Trading order if an entry is available, None otherwise
        """
        time_exit = date + timedelta(days=config.half_life_time_exit_factor * pair.half_life)

        if zscore >= config.entry_zscore:  # Short spread
            sl_zscore: float = config.stop_zscore_delta + zscore
            order = TradingOrder(pair=pair,
                                 signal=TradingSignal.SHORT_SPREAD,
                                 signal_date=date,
                                 zscore=zscore,
                                 stop_loss_zscore=sl_zscore,
                                 time_exit=time_exit)
            # Logging
            logger.debug(
                f"Entry signal SHORT_SPREAD for {pair.ticker_y}/{pair.ticker_x} (Z={zscore:+.2f})"
            )
            return order

        if zscore <= -config.entry_zscore:  # Long spread
            sl_zscore: float = zscore - config.stop_zscore_delta
            order = TradingOrder(pair=pair,
                                 signal=TradingSignal.LONG_SPREAD,
                                 signal_date=date,
                                 zscore=zscore,
                                 stop_loss_zscore=sl_zscore,
                                 time_exit=time_exit)
            # Logging
            logger.debug(
                f"Entry signal LONG_SPREAD for {pair.ticker_y}/{pair.ticker_x} (Z={zscore:+.2f})"
            )
            return order

        return None

    @staticmethod
    def _generate_exit_signal(position: PairPosition, zscore: float, date: datetime,
                              config: TradingConfig) -> TradingOrder | None:
        """
        Generates an exit signal based on zscore value and exit threshold
        :param position: The position to check
        :param zscore: The current zscore value
        :param date: The trading date
        :param config: The trading config
        :return: An order if exit needed or None
        """
        signal: TradingSignal = TradingSignal.HOLD
        # Check time exit
        if position.time_exit and date >= position.time_exit:
            signal = TradingSignal.EXIT

        # Stop loss
        if position.direction == TradingSignal.SHORT_SPREAD and zscore >= position.stop_loss_zscore:
            signal = TradingSignal.EXIT
        if position.direction == TradingSignal.LONG_SPREAD and zscore <= position.stop_loss_zscore:
            signal = TradingSignal.EXIT

        # Take profit
        if position.direction == TradingSignal.SHORT_SPREAD and zscore <= config.exit_zscore:
            signal = TradingSignal.EXIT
        if position.direction == TradingSignal.LONG_SPREAD and zscore >= -config.exit_zscore:
            signal = TradingSignal.EXIT

        return None if signal is TradingSignal.HOLD else TradingOrder(pair=position.pair_model,
                                                                      signal=TradingSignal.EXIT,
                                                                      signal_date=date,
                                                                      zscore=zscore)

    @staticmethod
    def _calculate_spread(
            pair: Pair,
            prices_y: list[float],
            prices_x: list[float],
    ) -> np.ndarray:
        """
        Calculates the current spread based on the data acquired at the pair selection time
        :param pair: The traded pair
        :param prices_y: Y asset's prices
        :param prices_x: X asset's prices
        :return: The estimated spread
        """
        return (
                np.log(prices_y)
                - pair.intercept
                - pair.hedge_ratio * np.log(prices_x)
        )

    @staticmethod
    def _calculate_zscore(spread: float, mean: float, std: float) -> float:
        """
        Calculates the current zscore
        :param spread: The current estimated spread
        :param mean: The spread's mean calculated at the pair selection step
        :param std: The spread's standard deviation calculated at the pair selection step
        :return: The zscore
        :raise ValueError: If std <= 0 or spread / mean not finite floats
        """
        VUtils.require_positive("std", std)
        VUtils.require_finite("spread", spread)
        VUtils.require_finite("mean", mean)

        return (spread - mean) / std

    @staticmethod
    def calculate_position_sizing(capital: float, price_y: float, price_x: float, hedge_ratio: float,
                                  direction: TradingSignal, quantity_step: float = 0.01) -> tuple[
        float, float]:
        """
        Calculates the position sizing based for a given capital and hedge ratio
        :param capital: The capital to trade
        :param price_y: Y asset's price
        :param price_x: X asset's price
        :param hedge_ratio: The hedge ratio
        :param direction: The trade's direction (Long or short spread)
        :param quantity_step: The number of decimals to round the quantities to
        :return: The signed quantities of asset y and x.
        :raises: ValueError if the given direction is invalid (Not long / short spread) or if the given numbers are not strictly positive
        """

        VUtils.require_positive("capital", capital)
        VUtils.require_finite("hedge_ratio", hedge_ratio)

        if hedge_ratio == 0:
            raise ValueError("Hedge ratio can't be 0.")

        VUtils.require_positive("quantity_step", quantity_step)
        for name, value in (("price_y", price_y), ("price_x", price_x)):
            VUtils.require_positive(name, value)

        if direction not in (
                TradingSignal.LONG_SPREAD,
                TradingSignal.SHORT_SPREAD,
        ):
            raise ValueError("Invalid trading direction.")

        beta_decimal: Decimal = Decimal(str(abs(hedge_ratio)))
        capital_decimal: Decimal = Decimal(str(capital))
        price_x_decimal: Decimal = Decimal(str(price_x))
        price_y_decimal: Decimal = Decimal(str(price_y))
        step_decimal: Decimal = Decimal(str(quantity_step))

        exposure_y: Decimal = capital_decimal / (1 + beta_decimal)
        exposure_x: Decimal = capital_decimal - exposure_y

        quantity_y = exposure_y / price_y_decimal
        quantity_x = exposure_x / price_x_decimal

        sign = 1 if direction == TradingSignal.LONG_SPREAD else -1
        beta_sign = 1 if hedge_ratio > 0 else -1

        quantity_y *= sign
        quantity_x *= -sign * beta_sign

        # Round quantities
        quantity_x = int(quantity_x / step_decimal) * step_decimal
        quantity_y = int(quantity_y / step_decimal) * step_decimal

        for name, value in (("quantity_y", quantity_y), ("quantity_x", quantity_x)):
            if not value.is_finite() or value == 0:
                raise ValueError(
                    f"{name} is invalid or zero after rounding."
                )

        return float(quantity_y), float(quantity_x)

    @staticmethod
    def process_pair(pair: Pair, prices: dict[str, list[float]], date: datetime,
                     config: TradingConfig, position: PairPosition | None = None) -> TradingOrder | None:
        """
        Generates entry or exit signals and create an order for the given pair
        Pre: Quantities are valide (Non 0)
        :param pair: The pair to trade
        :param prices: The current prices
        :param date: The trading date
        :param config: The trading configuration
        :param position: The current position. None if we are looking for an entry
        :return: A Trading order if a signal is found, otherwise None
        :raises: ValueError if the given direction is invalid (Not long / short spread)
        """
        prices_y = prices[pair.ticker_y]
        prices_x = prices[pair.ticker_x]

        spread: np.ndarray = TradingEngine._calculate_spread(
            pair=pair,
            prices_y=prices_y,
            prices_x=prices_x,
        )

        rolling_std: float = float(np.std(spread))

        if rolling_std < 1e-8:
            rolling_std = pair.spread_std

        zscore: float = TradingEngine._calculate_zscore(
            spread=spread[-1],
            mean=pair.spread_mean,
            std=rolling_std,
        )

        if position is not None:  # We look for an exit
            order: TradingOrder | None = TradingEngine._generate_exit_signal(
                position=position,
                zscore=zscore,
                date=date,
                config=config,
            )
        else:  # We look for an entry
            order: TradingOrder | None = TradingEngine._generate_entry_signal(
                zscore=zscore,
                pair=pair,
                config=config,
                date=date
            )

        return order
