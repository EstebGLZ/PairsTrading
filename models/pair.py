from dataclasses import dataclass

from utils.validation_utils import ValidationUtils as VUtils


@dataclass(frozen=True, slots=True)
class Pair:
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
        hurst_text = "N/A" if self.hurst is None else f"{self.hurst:.3f}"

        half_life_text = "N/A" if self.half_life is None else f"{self.half_life:.2f}"

        crossings_text = "N/A" if self.mean_crossings is None else f"{self.mean_crossings:.2f}"

        return (
            f"{self.ticker_y}/{self.ticker_x} "
            f"(pvalue={self.pvalue:.4g}, "
            f"test_stat={self.test_statistic:.3f}, "
            f"hedge_ratio={self.hedge_ratio:.3f}, "
            f"intercept={self.intercept:.3f}, "
            f"hurst={hurst_text}, "
            f"half_life={half_life_text}, "
            f"mean_crossings={crossings_text})"
        )

    @property
    def pair(self) -> tuple[str, str]:
        return self.ticker_y, self.ticker_x

    def __post_init__(self) -> None:
        if self.ticker_y == self.ticker_x:
            raise ValueError("A pair cannot consist of the same asset twice.")
        VUtils.require_positive("spread_std", self.spread_std)
        VUtils.require_finite("spread_mean", self.spread_mean)
        VUtils.require_finite("intercept", self.intercept)
        VUtils.require_finite("hedge_ratio", self.hedge_ratio)
        if self.hedge_ratio == 0:
            raise ValueError("Hedge ratio cannot be 0.")
