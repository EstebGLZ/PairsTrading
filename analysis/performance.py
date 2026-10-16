"""Daily equity analysis, independent of trading and portfolio accounting."""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from utils.validation_utils import ValidationUtils as VUtils


@dataclass
class PerformanceReport:
    """Ratios are decimal fractions; undefined metrics are None (JSON null)."""

    series: pd.DataFrame
    metrics: dict[str, float | int | None]
    periods_per_year: int
    annual_risk_free_rate: float
    warnings: list[str]

    def summary(self) -> str:
        labels = {
            "final_equity": "Final equity",
            "total_pnl": "Total PnL",
            "total_return": "Total return",
            "annualized_return": "Annualized return (sessions)",
            "annualized_volatility": "Annualized volatility",
            "sharpe_ratio": "Sharpe ratio (annualized)",
            "max_drawdown": "Maximum drawdown",
            "calmar_ratio": "Calmar ratio",
        }
        percentages = {"total_return", "annualized_return", "annualized_volatility", "max_drawdown"}
        lines = [f"Performance over {self.metrics['observations']} trading sessions"]
        for key, label in labels.items():
            value = self.metrics[key]
            formatted = "N/A" if value is None else (f"{value:.4%}" if key in percentages else f"{value:,.4f}")
            lines.append(f"{label}: {formatted}")
        lines.extend(f"Note: {warning}" for warning in self.warnings)
        return "\n".join(lines)

    def plot(self):
        """Return a standalone Matplotlib figure, without opening a GUI window."""
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from matplotlib.ticker import PercentFormatter

        figure = Figure(figsize=(11, 7), layout="constrained")
        FigureCanvasAgg(figure)
        equity_ax, drawdown_ax = figure.subplots(2, 1, sharex=True, height_ratios=[2, 1])
        equity_ax.plot(self.series.index, self.series["equity"], color="#2563eb", label="Daily equity")
        equity_ax.axhline(self.metrics["starting_capital"], color="#64748b", linestyle="--", label="Starting capital")
        equity_ax.set(title="Pairs trading — equity and drawdown", ylabel="Equity (account currency)")
        equity_ax.legend(loc="best")
        drawdown_ax.fill_between(self.series.index, self.series["drawdown"], 0, color="#dc2626", alpha=0.25)
        drawdown_ax.plot(self.series.index, self.series["drawdown"], color="#dc2626", linewidth=1)
        drawdown_ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
        drawdown_ax.set(ylabel="Drawdown", xlabel="Trading date")
        for axis in (equity_ax, drawdown_ax):
            axis.grid(alpha=0.2)
        figure.supxlabel("Based on recorded equity; includes open-position valuation. No additional costs applied.",
                         fontsize=9)
        return figure

    def export(self, directory: str | Path) -> Path:
        """Create a new report directory; never overwrite an earlier run."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        self.series.to_csv(directory / "equity.csv", index_label="Date")
        payload = {
            "start_date": self.series.index[0].isoformat(),
            "end_date": self.series.index[-1].isoformat(),
            "periods_per_year": self.periods_per_year,
            "annual_risk_free_rate": self.annual_risk_free_rate,
            "metrics": self.metrics,
            "warnings": self.warnings,
        }
        (directory / "summary.json").write_text(
            json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
        )
        figure = self.plot()
        figure.savefig(directory / "performance.png", dpi=150)
        figure.clear()
        return directory


class PerformanceAnalyzer:
    """Analyze consecutive daily close valuations, with no external cash flows.

    starting_capital is the equity immediately before the first recorded session.
    Every row is one trading session
    Pass only the trading period, not the formation window or a synthetic baseline row.
    """

    @staticmethod
    def analyze(
            equity: Mapping[datetime, float] | pd.Series,
            starting_capital: float,
            periods_per_year: int = 252,
            annual_risk_free_rate: float = 0.0,
    ) -> PerformanceReport:
        VUtils.require_positive("starting_capital", starting_capital)
        if not isinstance(periods_per_year, int) or isinstance(periods_per_year, bool) or periods_per_year <= 0:
            raise ValueError("periods_per_year must be a positive integer.")
        if not math.isfinite(annual_risk_free_rate) or annual_risk_free_rate <= -1:
            raise ValueError("annual_risk_free_rate must be finite and greater than -1.")

        values = pd.Series(equity, dtype=float, copy=True)
        if values.empty:
            raise ValueError("Cannot analyze an empty equity history.")
        if pd.api.types.is_numeric_dtype(values.index.dtype):
            raise ValueError("Equity must be indexed by trading dates.")
        values.index = pd.DatetimeIndex(pd.to_datetime(values.index))
        if values.index.hasnans or values.index.normalize().has_duplicates:
            raise ValueError("Equity must contain one valid observation per trading date.")
        values = values.sort_index().rename("equity")
        if not np.isfinite(values.to_numpy()).all():
            raise ValueError("Equity contains non-finite values; missing sessions must not be filled silently.")

        previous = values.shift(1)
        previous.iloc[0] = starting_capital
        returns = values / previous.where(previous > 0) - 1
        
        # Initial capital prevents hiding a loss on the very first day.
        high_water_mark = values.cummax().clip(lower=starting_capital)
        drawdown = values / high_water_mark - 1
        series = pd.DataFrame({
            "equity": values,
            "daily_return": returns,
            "cumulative_return": values / starting_capital - 1,
            "high_water_mark": high_water_mark,
            "drawdown": drawdown,
        })
        observations = len(values)
        final_equity = float(values.iloc[-1])
        max_drawdown = float(drawdown.min())
        annualized_return = volatility = sharpe = calmar = None
        warnings = []
        if observations < periods_per_year:
            warnings.append("Less than one year of observations; annualized statistics may be unstable.")
        if (values <= 0).any():
            warnings.append(
                "Equity reached zero or became negative: annualized return, volatility, Sharpe and Calmar are unavailable.")
        else:
            annualized_return = math.expm1(math.log(final_equity / starting_capital) * periods_per_year / observations)
            if observations >= 2:
                daily_std = float(returns.std(ddof=1))
                volatility = daily_std * math.sqrt(periods_per_year)
                if daily_std > 1e-12:
                    daily_rf = math.expm1(math.log1p(annual_risk_free_rate) / periods_per_year)
                    sharpe = float((returns.mean() - daily_rf) / daily_std * math.sqrt(periods_per_year))
                else:
                    warnings.append("Sharpe unavailable: daily return volatility is zero or numerically negligible.")
            else:
                warnings.append("At least two returns are required for sample volatility and Sharpe.")
            if max_drawdown < 0:
                calmar = annualized_return / abs(max_drawdown)

        metrics = {
            "observations": observations,
            "starting_capital": float(starting_capital),
            "final_equity": final_equity,
            "total_pnl": final_equity - starting_capital,
            "total_return": final_equity / starting_capital - 1,
            "annualized_return": annualized_return,
            "annualized_volatility": volatility,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "calmar_ratio": calmar,
        }
        return PerformanceReport(series, metrics, periods_per_year, annual_risk_free_rate, warnings)
