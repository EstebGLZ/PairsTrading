import json
import logging
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from engine.portfolio import Portfolio
from models import PairPosition, Report

logger = logging.getLogger(__name__)


class Statistics:
    """
    Class computing statistics and visualizations about the portfolio's performances.
    """

    def __init__(self, portfolio: Portfolio, periods_per_year: int, annual_risk_free_rate: float) -> None:
        if not portfolio.equity:
            raise ValueError("Cannot analyze an empty equity history.")

        self._equity: dict[datetime, float] = portfolio.equity
        self._starting_capital: float = portfolio.starting_capital
        self._trades: list[PairPosition] = portfolio.closed_positions
        self._ongoing_trades: dict[tuple[str, str], PairPosition] = portfolio.open_positions
        self._periods_per_year: int = periods_per_year
        self._annual_risk_free_rate: float = annual_risk_free_rate
        self._warnings: list[str] = []
        self._report: Report = Report()
        self._series: pd.DataFrame | None = None

        # Basic values to the report
        self._report.n_observations = len(self._equity)
        self._report.starting_capital = self._starting_capital
        self._report.final_equity = next(reversed(self._equity.values()))

    def summary(self) -> Report:
        """Calculate stats and log summary."""
        self._calculate_trades_stats()
        self._calculate_equity_stats()

        # Logging
        for warning in self._warnings:
            logger.warning(warning)
        logger.info(f"\n\n{self._report}")
        return self._report

    def _calculate_equity_stats(self) -> None:
        """
        Calculate metrics about the equity and add them to the report
        :return: None
        """
        values = pd.Series(self._equity, dtype=float, copy=True)
        previous = values.shift(1)
        previous.iloc[0] = self._starting_capital
        returns = values / previous.where(previous > 0) - 1

        high_water_mark = values.cummax().clip(lower=self._starting_capital)
        drawdown = values / high_water_mark - 1
        max_drawdown: float = float(drawdown.min())
        observations = len(values)
        final_equity = float(values.iloc[-1])
        annualized_return = volatility = sharpe = calmar = float('nan')

        if observations < self._periods_per_year:
            self._warnings.append("Less than one year of observations; annualized statistics may be unstable.")

        if (values <= 0).any():
            self._warnings.append("Equity reached zero or became negative: ratios are unavailable.")
        else:
            annualized_return = math.expm1(
                math.log(final_equity / self._starting_capital) * self._periods_per_year / observations)
            if observations >= 2:
                daily_std = float(returns.std(ddof=1))
                volatility = daily_std * math.sqrt(self._periods_per_year)
                if daily_std > 1e-12:
                    daily_rf = math.expm1(math.log1p(self._annual_risk_free_rate) / self._periods_per_year)
                    sharpe = float((returns.mean() - daily_rf) / daily_std * math.sqrt(self._periods_per_year))
                else:
                    self._warnings.append("Sharpe unavailable: volatility is negligible.")
            else:
                self._warnings.append("At least two returns are required for sample volatility and Sharpe.")
            if max_drawdown < 0:
                calmar = annualized_return / abs(max_drawdown)

        # Populate report object
        self._report.total_pnl = final_equity - self._starting_capital
        self._report.total_return = final_equity / self._starting_capital - 1
        self._report.annualized_return = annualized_return
        self._report.annualized_volatility = volatility
        self._report.sharpe_ratio = sharpe
        self._report.max_drawdown = max_drawdown
        self._report.calmar_ratio = calmar

        # Store series for plotting and exporting
        self._series = pd.DataFrame({
            "equity": values,
            "daily_return": returns,
            "cumulative_return": values / self._starting_capital - 1,
            "high_water_mark": high_water_mark,
            "drawdown": drawdown,
        })

    def _calculate_trades_stats(self) -> None:
        """
        Calculate metrics about the trades and add them to the report
        :return: None
        """
        if not self._trades:
            return
        profits = [pos.realized_pnl for pos in self._trades if pos.realized_pnl > 0]
        losses = [pos.realized_pnl for pos in self._trades if pos.realized_pnl <= 0]
        total_trades = len(self._trades)

        winrate = len(profits) / total_trades if total_trades > 0 else float('nan')
        lossrate = 1.0 - winrate if not math.isnan(winrate) else float('nan')

        mean_profit = float(np.mean(profits)) if profits else 0.0
        mean_loss = float(np.mean(losses)) if losses else 0.0

        sum_profits = float(np.sum(profits)) if profits else 0.0
        sum_losses = abs(float(np.sum(losses))) if losses else 0.0

        profit_factor = (sum_profits / sum_losses) if sum_losses > 0 else (
            float("inf") if sum_profits > 0 else float('nan'))
        payoff_ratio = (mean_profit / abs(mean_loss)) if abs(mean_loss) > 0 else (
            float("inf") if mean_profit > 0 else float('nan'))

        durations = [(pos.exit_date - pos.entry_date).days for pos in self._trades if pos.exit_date and pos.entry_date]
        avg_holding_duration = float(np.mean(durations)) if durations else float('nan')
        expectancy = (winrate * mean_profit + lossrate * mean_loss) if not math.isnan(winrate) else float('nan')
        total_cost = sum([trade.total_cost for trade in self._trades])

        # Populate report object
        self._report.winrate = winrate
        self._report.profit_factor = profit_factor
        self._report.payoff_ratio = payoff_ratio
        self._report.avg_holding_duration = avg_holding_duration
        self._report.expectancy = expectancy
        self._report.total_cost = total_cost

    def _calculate_annual_returns(self) -> dict[str, float]:
        """Compute calendar year returns
        :return dict[str, float]: A dict with the year as a key and the year's return as a percentage
        """
        if self._series is None:
            return {}

        grouped = self._series.groupby(self._series.index.year)
        annual_returns: dict[str, float] = {}
        prev_equity = self._starting_capital
        for year, group in grouped:
            last_equity = group["equity"].iloc[-1]
            ret = (last_equity - prev_equity) / prev_equity
            # Avoid plotting meaningless bar
            if len(group) > 5 or ret != 0.0:
                annual_returns[str(year)] = ret
            prev_equity = last_equity

        return annual_returns

    def plot(self) -> Figure:
        """Generate Matplotlib figure with equity and drawdown curves."""
        if self._series is None:
            self._calculate_equity_stats()

        figure = Figure(figsize=(11, 10), layout="constrained")
        FigureCanvasAgg(figure)

        gs = figure.add_gridspec(3, 1, height_ratios=[2.2, 1.2, 1.4])
        equity_ax = figure.add_subplot(gs[0, 0])
        drawdown_ax = figure.add_subplot(gs[1, 0], sharex=equity_ax)
        annual_ax = figure.add_subplot(gs[2, 0])

        # Equity plot
        equity_ax.plot(self._series.index, self._series["equity"], color="#2563eb", label="Daily equity")
        equity_ax.axhline(self._starting_capital, color="#64748b", linestyle="--", label="Starting capital")
        equity_ax.set(title="Pairs trading — equity and drawdown", ylabel="Equity (account currency)")
        equity_ax.legend(loc="best")
        equity_ax.grid(alpha=0.2)

        # Drawdown plot
        drawdown_ax.fill_between(self._series.index, self._series["drawdown"], 0, color="#dc2626", alpha=0.25)
        drawdown_ax.plot(self._series.index, self._series["drawdown"], color="#dc2626", linewidth=1)
        drawdown_ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
        drawdown_ax.set(ylabel="Drawdown", xlabel="Trading date")
        drawdown_ax.grid(alpha=0.2)

        figure.supxlabel("Based on recorded equity; includes open-position valuation.",
                         fontsize=9)

        annual_returns = self._calculate_annual_returns()
        if annual_returns:
            years = list(annual_returns.keys())
            returns = list(annual_returns.values())

            # Vert (#16a34a) si >= 0, Rouge (#dc2626) si < 0
            colors = ["#16a34a" if r >= 0 else "#dc2626" for r in returns]

            bars = annual_ax.bar(years, returns, color=colors, width=0.55, edgecolor="black", linewidth=0.5)
            annual_ax.axhline(0, color="#64748b", linewidth=0.8, linestyle="--")
            annual_ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
            annual_ax.set_ylabel("Annual return")
            annual_ax.set_title("Annual returns breakdown", fontsize=11, fontweight="bold")
            annual_ax.grid(axis="y", alpha=0.2)
            for bar, r in zip(bars, returns):
                y_val = bar.get_height()
                offset = 0.002 if y_val >= 0 else -0.004
                va = "bottom" if y_val >= 0 else "top"
                text_color = "#15803d" if y_val >= 0 else "#b91c1c"

                annual_ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    y_val + offset,
                    f"{r * 100:+.2f}%",
                    ha="center",
                    va=va,
                    fontsize=9,
                    fontweight="bold",
                    color=text_color
                )

            y_min = min(returns) if returns else 0
            y_max = max(returns) if returns else 0
            annual_ax.set_ylim(min(y_min * 1.35, -0.02), max(y_max * 1.35, 0.02))
        return figure

    def export(self, directory: str | Path) -> Path:
        """Export CSV series, PNG figure, and JSON summary to directory.
           statistics.summary is expected to be run before this"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)

        # Export equity evolution
        if self._series is not None:
            self._series.to_csv(directory / "equity.csv", index_label="Date")

        # Export positions
        if self._trades:
            trades_records = [
                {
                    "pair": f"{pos.pair[0]}/{pos.pair[1]}",
                    "direction": pos.direction.name,
                    "entry_date": pos.entry_date.strftime("%Y-%m-%d"),
                    "exit_date": pos.exit_date.strftime("%Y-%m-%d"),
                    "duration_days": pos.holding_duration,
                    "entry_zscore": round(pos.entry_zscore, 3),
                    "exit_zscore": round(pos.exit_zscore, 3) if pos.exit_zscore is not None else None,
                    "entry_exposure": round(pos.entry_gross_exposure, 2),
                    "gross_pnl": round(pos.gross_pnl, 2),
                    "commission": round(pos.total_commission, 2),
                    "slippage": round(pos.total_slippage, 2),
                    "borrow_fees": round(pos.borrow_fees, 2),
                    "total_cost": round(pos.total_cost, 2),
                    "net_pnl": round(pos.realized_pnl, 2),
                    "net_return_pct": round(pos.realized_return * 100, 3),
                }
                for pos in self._trades
            ]
            pd.DataFrame(trades_records).to_csv(directory / "trades.csv", index=False)

        # Export Figure
        figure = self.plot()
        figure.savefig(directory / "performance.png", dpi=200)
        figure.savefig(directory / "performance.svg")
        figure.clear()

        # Export JSON summary
        payload = {
            "start_date": self._series.index[0].isoformat() if self._series is not None else None,
            "end_date": self._series.index[-1].isoformat() if self._series is not None else None,
            "periods_per_year": self._periods_per_year,
            "annual_risk_free_rate": self._annual_risk_free_rate,
            "metrics": {k: getattr(self._report, k) for k in self._report.__dataclass_fields__},
            "warnings": self._warnings,
        }
        (directory / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        logger.info("Performance report saved to %s", directory)
        return directory
