from models.pair import PairResult
from models.trading import TradingSignal
import pandas as pd
import numpy as np


class TradingEngine:
    
    @staticmethod
    def generate_entry_signal(zscore: float,entry_threshold: float = 2.0) -> TradingSignal:
        if zscore >= entry_threshold:
            return TradingSignal.SHORT_SPREAD

        if zscore <= -entry_threshold:
            return TradingSignal.LONG_SPREAD

        return TradingSignal.HOLD
    
    @staticmethod
    def generate_exit_signal(zscore: float,exit_threshold: float = 0.0, sl_threshhold:float = 3.5) -> TradingSignal:
        if abs(zscore) <= exit_threshold or abs(zscore) >= sl_threshhold:
            return TradingSignal.EXIT
        return TradingSignal.HOLD
    
    @staticmethod
    def _calculate_spread(
        pair: PairResult,
        log_price_y: float,
        log_price_x: float,
    ) -> float:
        return (
            log_price_y
            - pair.intercept
            - pair.hedge_ratio * log_price_x
        )
    @staticmethod
    def _calculate_zscore(spread: float, mean:float, std:float) -> float:
        return (spread - mean) / std
    
