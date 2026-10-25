from dataclasses import dataclass

from utils.validation_utils import ValidationUtils as VUtils


@dataclass(frozen=True, slots=True)
class PairSelectionConfig:
    n_components: int = 5
    min_coverage: float = 0.95
    min_samples: int = 3

    significance_level: float = 0.05

    max_hurst: float = 0.5

    min_half_life: float = 1.0
    max_half_life: float = 365.0

    min_crossings: float = 12.0

    def __post_init__(self) -> None:
        VUtils.require_positive("n_components", self.n_components)
        VUtils.require_positive("min_samples", self.min_samples)
        VUtils.require_positive("min_half_life", self.min_half_life, False)
        VUtils.require_positive("max_half_life", self.max_half_life, False)
        VUtils.require_positive("min_crossings", self.min_crossings, False)

        if not 0 < self.min_coverage <= 1:
            raise ValueError("min_coverage must be between 0 and 1.")

        if self.min_samples < 2:
            raise ValueError("min_samples must be >= 2.")

        if not 0 < self.significance_level < 1:
            raise ValueError("significance_level must be between 0 and 1.")

        if not 0 < self.max_hurst <= 1:
            raise ValueError("max_hurst must be between 0 and 1.")

        if self.max_half_life <= self.min_half_life:
            raise ValueError("max_half_life must be greater than min_half_life.")


@dataclass(frozen=True, slots=True)
class TradingConfig:
    entry_zscore: float = 2.5  # zscore to trigger an entry
    exit_zscore: float = 0.0  # zscore to trigger an exit
    stop_zscore_delta: float = 1.0  # zscore delta to trigger a stop loss (entry_zscore + stop_zscore_delta)
    half_life_time_exit_factor: float = 3.0  # Time exit factor based on half life value
    zscore_window: int = 30  # zscore calculation rolling window
    max_position: int = 10  # How many position to trade at once
    pairs_top_n: int = 5  # The best n pairs to select for trading
    allocation_per_pair: float = 0.1  # Allocation of the portfolio per pair

    def __post_init__(self):
        # Check strictly positive floats
        for name, value in (("stop_zscore_delta", self.stop_zscore_delta),
                            ("half_life_time_exit_factor", self.half_life_time_exit_factor),
                            ("zscore_window", self.zscore_window),
                            ("max_position", self.max_position),
                            ("pairs_top_n", self.pairs_top_n)):
            VUtils.require_positive(name, value)

        # Check trading thresholds coherence
        VUtils.require_finite("entry_zscore", self.entry_zscore)
        VUtils.require_finite("exit_zscore", self.exit_zscore)
        if not (0 <= self.exit_zscore < self.entry_zscore):
            raise ValueError("Expected 0 <= exit_zscore < entry_zscore.")

        # Check allocation coherence
        if not (0 < self.allocation_per_pair <= 1.0):
            raise ValueError("Expected 0 < allocation_per_pair <= 1.0.")


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    formation_window: int = 252
    trading_window: int = 20
    starting_capital: int = 10_000
    commission_pct: float = 0.0005
    slippage_pct: float = 0.0005
    borrow_rate: float = 0.01

    def __post_init__(self) -> None:
        for name, value in (
                ("formation_window", self.formation_window),
                ("trading_window", self.trading_window),
                ("starting_capital", self.starting_capital)):
            VUtils.require_positive(name, value)

        for name, value in (
                ("commission_pct", self.commission_pct),
                ("slippage_pct", self.slippage_pct),
                ("borrow_rate", self.borrow_rate)):
            VUtils.require_positive(name, value, strict=False)

        if self.formation_window <= self.trading_window:
            raise ValueError("formation_window must be greater than trading_window.")
