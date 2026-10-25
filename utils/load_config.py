import json
import logging
from datetime import datetime

from models import PairSelectionConfig, TradingConfig, BacktestConfig

logger = logging.getLogger(__name__)


class Configuration:
    CONFIGURATION_FOLDER: str = "./config"
    STOCKS_KEY: str = "stocks"
    START_DATE_KEY: str = "start"
    END_DATE_KEY: str = "end"
    PAIR_SELECTION_CONFIG_KEY: str = "pair_selection"
    TRADING_CONFIG_KEY: str = "trading_config"
    BACKTEST_CONFIG_KEY: str = "backtest_config"

    def __init__(self):
        self.config = None

    def load_config(self, name: str) -> None:
        with open(f"{self.CONFIGURATION_FOLDER}/{name}") as file:
            self.config = json.load(file)

        logger.info(f"Loaded {name} configuration")

    def get_stocks(self) -> list[str]:
        self._check_config("get_stocks")
        return self.config[self.STOCKS_KEY]

    def get_start_date(self) -> datetime:
        self._check_config("get_start_date")
        return datetime.strptime(self.config[self.START_DATE_KEY], "%Y-%m-%d")

    def get_end_date(self) -> datetime:
        self._check_config("get_end_date")
        return datetime.strptime(self.config[self.END_DATE_KEY], "%Y-%m-%d")

    def get_pair_selection_config(self) -> PairSelectionConfig:
        self._check_config("get_pair_selection_config")
        return PairSelectionConfig(**self.config[self.PAIR_SELECTION_CONFIG_KEY])

    def get_trading_config(self) -> TradingConfig:
        self._check_config("get_trading_config")
        return TradingConfig(**self.config[self.TRADING_CONFIG_KEY])

    def get_backtest_config(self) -> BacktestConfig:
        self._check_config("get_backtest_config")
        return BacktestConfig(**self.config[self.BACKTEST_CONFIG_KEY])

    def _check_config(self, method):
        if self.config is None:
            raise RuntimeError(f"You must load the configuration file before calling {method}")
