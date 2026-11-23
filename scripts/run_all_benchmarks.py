import os
import sys
import shutil
import pickle
import logging
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from engine.backtest_engine import BacktestEngine
from engine.pair_engine import PairEngine
from analysis.statistics import Statistics
from utils.load_config import Configuration
from models.configuration import BacktestConfig, TradingConfig, PairSelectionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BenchmarkRunner")

# 1. Setup persistent pair selection cache
PAIRS_CACHE_FILE = Path("./cache/pairs_cache.pkl")
_pairs_cache = {}
if PAIRS_CACHE_FILE.exists():
    try:
        with open(PAIRS_CACHE_FILE, "rb") as f:
            _pairs_cache = pickle.load(f)
        logger.info(f"Loaded {len(_pairs_cache)} cached formation windows from {PAIRS_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Could not load pairs cache: {e}")

_original_select = PairEngine.select_pairs

def cached_select_pairs(data, config):
    start = data.index.get_level_values("Date").min()
    end = data.index.get_level_values("Date").max()
    key = (start, end, config.n_components, config.significance_level, config.max_hurst, config.min_half_life, config.max_half_life, config.min_crossings)
    if key not in _pairs_cache:
        _pairs_cache[key] = _original_select(data, config)
        try:
            with open(PAIRS_CACHE_FILE, "wb") as f:
                pickle.dump(_pairs_cache, f)
        except Exception:
            pass
    return list(_pairs_cache[key])

PairEngine.select_pairs = cached_select_pairs


def main():
    logger.info("Starting automated benchmark execution for all runs...")

    # Load stocks and base configs
    cfg_loader = Configuration()
    cfg_loader.load_config("config_in_sample.json")
    stocks = cfg_loader.get_stocks()
    pair_selection_cfg = cfg_loader.get_pair_selection_config()

    # Dates
    in_sample_start = datetime(2010, 1, 1)
    in_sample_end = datetime(2020, 12, 31)

    oos_start = datetime(2020, 1, 1)
    oos_end = datetime(2026, 9, 30)

    # 12 In-Sample configurations (test.xlsx)
    in_sample_runs = [
        {"id": "run_01", "entry": 3.5, "exit": 0.25, "sl": 1.0, "z_win": 30, "t_win": 20},
        {"id": "run_02", "entry": 3.5, "exit": 0.00, "sl": 1.0, "z_win": 30, "t_win": 20},
        {"id": "run_03", "entry": 3.0, "exit": 0.25, "sl": 1.0, "z_win": 30, "t_win": 20},
        {"id": "run_04", "entry": 3.0, "exit": 0.00, "sl": 1.0, "z_win": 30, "t_win": 20},
        {"id": "run_05", "entry": 2.5, "exit": 0.25, "sl": 1.0, "z_win": 30, "t_win": 20},
        {"id": "run_06", "entry": 2.5, "exit": 0.00, "sl": 1.0, "z_win": 30, "t_win": 20},
        {"id": "run_07", "entry": 3.0, "exit": 0.25, "sl": 1.5, "z_win": 30, "t_win": 20},
        {"id": "run_08", "entry": 3.0, "exit": 0.25, "sl": 0.5, "z_win": 30, "t_win": 20},
        {"id": "run_09", "entry": 3.0, "exit": 0.25, "sl": 1.5, "z_win": 60, "t_win": 20},
        {"id": "run_10", "entry": 3.0, "exit": 0.25, "sl": 1.5, "z_win": 15, "t_win": 20},
        {"id": "run_11", "entry": 3.0, "exit": 0.25, "sl": 1.5, "z_win": 30, "t_win": 40},
        {"id": "run_12", "entry": 3.0, "exit": 0.25, "sl": 1.5, "z_win": 30, "t_win": 10},
    ]

    # 2 Out-of-Sample configurations
    oos_runs = [
        {"id": "run_oos_gross", "entry": 3.0, "exit": 0.25, "sl": 1.5, "z_win": 30, "t_win": 10, "comm": 0.0, "slip": 0.0, "borrow": 0.0},
        {"id": "run_oos_net", "entry": 3.0, "exit": 0.25, "sl": 1.5, "z_win": 30, "t_win": 10, "comm": 0.0005, "slip": 0.0003, "borrow": 0.01},
    ]

    # Clean reports folder as requested
    reports_dir = Path("./reports")
    if reports_dir.exists():
        for item in reports_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
                logger.info(f"Deleted old report directory: {item.name}")
    reports_dir.mkdir(parents=True, exist_ok=True)

    results = []

    # Execute In-Sample runs
    for run in in_sample_runs:
        run_name = run["id"]
        logger.info(f"--- Executing {run_name} (In-Sample: Entry={run['entry']}, Exit={run['exit']}, SL={run['sl']}, Z-Win={run['z_win']}, Trade-Win={run['t_win']}) ---")
        
        btest_cfg = BacktestConfig(
            formation_window=252,
            trading_window=run["t_win"],
            starting_capital=10000.0,
            commission_pct=0.0,
            slippage_pct=0.0,
            borrow_rate=0.0
        )
        trading_cfg = TradingConfig(
            entry_zscore=run["entry"],
            exit_zscore=run["exit"],
            stop_zscore_delta=run["sl"],
            half_life_time_exit_factor=3.0,
            zscore_window=run["z_win"],
            max_position=10,
            pairs_top_n=5,
            allocation_per_pair=0.15
        )

        engine = BacktestEngine(
            stocks=stocks,
            start_date=in_sample_start,
            end_date=in_sample_end,
            config=btest_cfg
        )
        engine.start(pair_config=pair_selection_cfg, trading_config=trading_cfg)

        stats = Statistics(portfolio=engine.portfolio, periods_per_year=252, annual_risk_free_rate=0.0)
        report = stats.summary()
        stats.export(reports_dir / run_name)

        results.append({
            "Run": run_name,
            "Type": "In-Sample",
            "Return (%)": round(report.total_return * 100, 4),
            "Sharpe": round(report.sharpe_ratio, 4),
            "Max DD (%)": round(report.max_drawdown * 100, 4),
            "Winrate (%)": round(report.winrate * 100, 2),
            "PF": round(report.profit_factor, 3),
            "Trades": report.n_trades
        })

    # Execute Out-of-Sample runs
    for run in oos_runs:
        run_name = run["id"]
        logger.info(f"--- Executing {run_name} (Out-of-Sample: Comm={run['comm']}, Slip={run['slip']}, Borrow={run['borrow']}) ---")
        
        btest_cfg = BacktestConfig(
            formation_window=252,
            trading_window=run["t_win"],
            starting_capital=10000.0,
            commission_pct=run["comm"],
            slippage_pct=run["slip"],
            borrow_rate=run["borrow"]
        )
        trading_cfg = TradingConfig(
            entry_zscore=run["entry"],
            exit_zscore=run["exit"],
            stop_zscore_delta=run["sl"],
            half_life_time_exit_factor=3.0,
            zscore_window=run["z_win"],
            max_position=10,
            pairs_top_n=5,
            allocation_per_pair=0.15
        )

        engine = BacktestEngine(
            stocks=stocks,
            start_date=oos_start,
            end_date=oos_end,
            config=btest_cfg
        )
        engine.start(pair_config=pair_selection_cfg, trading_config=trading_cfg)

        stats = Statistics(portfolio=engine.portfolio, periods_per_year=252, annual_risk_free_rate=0.0)
        report = stats.summary()
        stats.export(reports_dir / run_name)

        results.append({
            "Run": run_name,
            "Type": "Out-of-Sample",
            "Return (%)": round(report.total_return * 100, 4),
            "Sharpe": round(report.sharpe_ratio, 4),
            "Max DD (%)": round(report.max_drawdown * 100, 4),
            "Winrate (%)": round(report.winrate * 100, 2),
            "PF": round(report.profit_factor, 3),
            "Trades": report.n_trades
        })

    logger.info("=" * 60)
    logger.info("ALL BENCHMARKS SUCCESSFULLY EXECUTED")
    logger.info("=" * 60)
    df_results = pd.DataFrame(results)
    print("\nSUMMARY OF EXECUTED BENCHMARKS:")
    print(df_results.to_string(index=False))

    # Save summary table
    df_results.to_csv(reports_dir / "benchmarks_summary.csv", index=False)
    logger.info(f"Saved global benchmark summary to {reports_dir / 'benchmarks_summary.csv'}")


if __name__ == "__main__":
    main()
