from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class PairResult:
    ticker_y: str
    ticker_x: str

    pvalue: float
    test_statistic: float

    hedge_ratio: float
    intercept: float

    hurst: float | None = None
    half_life: float | None = None
    mean_crossings: float | None = None


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
        if self.n_components <= 0:
            raise ValueError(
                "n_components must be > 0."
            )

        if not 0 < self.min_coverage <= 1:
            raise ValueError(
                "min_coverage must be between 0 and 1."
            )

        if self.min_samples < 2:
            raise ValueError(
                "min_samples must be >= 2."
            )

        if not 0 < self.significance_level < 1:
            raise ValueError(
                "significance_level must be between 0 and 1."
            )

        if not 0 < self.max_hurst <= 1:
            raise ValueError(
                "max_hurst must be between 0 and 1."
            )

        if self.min_half_life < 0:
            raise ValueError(
                "min_half_life must be >= 0."
            )

        if self.max_half_life <= self.min_half_life:
            raise ValueError(
                "max_half_life must be greater than min_half_life."
            )

        if self.min_crossings < 0:
            raise ValueError(
                "min_crossings must be >= 0."
            )