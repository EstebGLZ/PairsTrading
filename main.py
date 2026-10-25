import logging
from datetime import datetime, timezone

from analysis.statistics import Statistics
from engine.backtest_engine import BacktestEngine
from utils.load_config import Configuration

logger = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )


def main() -> None:
    setup_logging()

    config = Configuration()
    config.load_config("config.json")

    engine: BacktestEngine = BacktestEngine(stocks=config.get_stocks(),
                                            start_date=config.get_start_date(),
                                            end_date=config.get_end_date(),
                                            config=config.get_backtest_config())

    engine.start(pair_config=config.get_pair_selection_config(),
                 trading_config=config.get_trading_config())

    logger.info(engine.portfolio)

    stats: Statistics = Statistics(portfolio=engine.portfolio, periods_per_year=252, annual_risk_free_rate=0.0)
    stats.summary()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    stats.export(f"./reports/{run_id}")


if __name__ == "__main__":
    main()
