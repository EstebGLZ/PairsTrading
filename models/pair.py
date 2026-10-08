from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class PairResult:
    ticker_y: str
    ticker_x: str

    pvalue: float
    test_statistic: float

    hedge_ratio: float
    intercept: float
    
    spread_mean: float
    spread_std: float
    
    hurst: float | None = None
    half_life: float | None = None
    mean_crossings: float | None = None
    
    def __str__(self) -> str:
        return (
            f"{self.ticker_y}/{self.ticker_x} "
            f"(pvalue={self.pvalue:.4g}, "
            f"test_stat={self.test_statistic:.3f}, "
            f"hedge_ratio={self.hedge_ratio:.3f}, "
            f"intercept={self.intercept:.3f}, "
            f"hurst={self.hurst:.3f if self.hurst is not None else 'N/A'}, "
            f"half_life={self.half_life:.2f if self.half_life is not None else 'N/A'}, "
            f"mean_crossings={self.mean_crossings:.2f if self.mean_crossings is not None else 'N/A'})"
        )

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
            
    def __str__(self) -> str:
        return (
            f"PairSelectionConfig("
            f"n_components={self.n_components}, "
            f"min_coverage={self.min_coverage}, "
            f"min_samples={self.min_samples}, "
            f"significance_level={self.significance_level}, "
            f"max_hurst={self.max_hurst}, "
            f"half_life=[{self.min_half_life}, {self.max_half_life}], "
            f"min_crossings={self.min_crossings}"
            f")"
        )