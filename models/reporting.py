from dataclasses import dataclass


@dataclass
class Report:
    n_observations: float = float('nan')
    starting_capital: float = float('nan')
    final_equity: float = float('nan')
    total_pnl: float = float('nan')
    total_return: float = float('nan')
    annualized_return: float = float('nan')
    annualized_volatility: float = float('nan')
    sharpe_ratio: float = float('nan')
    max_drawdown: float = float('nan')
    calmar_ratio: float = float('nan')
    winrate: float = float('nan')
    profit_factor: float = float('nan')
    payoff_ratio: float = float('nan')
    avg_holding_duration: float = float('nan')
    expectancy: float = float('nan')

    def __str__(self) -> str:
        return (f"{'=' * 3} Report {'=' * 3}\n"
                f"Number of observations: {self.n_observations}\n"
                f"Starting Capital: {self.starting_capital:.4f}\n"
                f"Final Equity: {self.final_equity:.4f}\n"
                f"Total PnL: {self.total_pnl:.4f}\n"
                f"Total Return: {self.total_return:.4%}\n"
                f"Annualized Return: {self.annualized_return:.4%}\n"
                f"Annualized Volatility: {self.annualized_volatility:.4%}\n"
                f"Sharpe Ratio: {self.sharpe_ratio:.4f}\n"
                f"Max Drawdown: {self.max_drawdown:.4%}\n"
                f"Calmar Ratio: {self.calmar_ratio:.4f}\n"
                f"Winrate: {self.winrate:.4%}\n"
                f"Profit Factor: {self.profit_factor:.4f}\n"
                f"Payoff Ratio: {self.payoff_ratio:.4f}\n"
                f"Average Holding Duration (days): {self.avg_holding_duration:.4f}\n"
                f"Expected Return: {self.expectancy:.4f}"
                )
