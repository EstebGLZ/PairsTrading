import logging
from itertools import combinations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.cluster import OPTICS
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.stattools import coint

from data.columns import Feature
from models.pair import PairResult, PairSelectionConfig

logger = logging.getLogger(__name__)


class PairEngine:
    """
    This class is responsible for pairs engineering. It calculates all the features need to create pair and select the best ones
    """

    @staticmethod
    def select_pairs(data: pd.DataFrame, config: PairSelectionConfig) -> list[PairResult]:
        """
        Main method to create pairs
        :param data: The assets' data
        :param config: The config for selection the pairs
        :return: A list with all the possible pairs
        """
        logger.debug("Selecting pairs...")
        returns = PairEngine._align_returns(
            data=data,
            min_coverage=config.min_coverage,
        )

        pca_features, pca = PairEngine._calculate_pca(
            returns=returns,
            n_components=config.n_components,
        )

        clusters = PairEngine._cluster(
            pca_features=pca_features, min_samples=config.min_samples
        )

        candidates = PairEngine._generate_candidate_pairs(clusters=clusters)

        validated_pairs = PairEngine._validate_candidates(
            candidates=candidates, data=data, config=config
        )

        logger.debug(f"Final pairs: {len(validated_pairs)}")
        return validated_pairs

    @staticmethod
    def rank_pairs(pairs: list[PairResult], top_n: int = 5) -> list[PairResult]:
        """
        Rank the generated pairs by their mean crossing, half live and pvalue
        :param pairs: The available pairs
        :param top_n: How many pairs to select
        :return: The first n pairs
        """
        if top_n <= 0:
            raise ValueError("top_n must be positive.")

        return sorted(
            pairs,
            key=lambda p: (
                -p.mean_crossings,
                p.half_life,
                p.pvalue,
                p.ticker_y,
                p.ticker_x,
            ),
        )[:top_n]

    @staticmethod
    def _align_returns(data: pd.DataFrame, min_coverage: float = 0.95) -> pd.DataFrame:
        """
        Align the asset's return
        :param data: The asset DF
        :param min_coverage: How many trading should an asset have to be considered as tradable
        :return: The aligned returns
        """
        if Feature.DAILY_LOG_RETURNS not in data.columns:
            raise RuntimeError(
                "Daily log returns must be calculated before aligning returns."
            )

        # Filter only usable tickers
        returns = data[Feature.DAILY_LOG_RETURNS].unstack("Ticker")
        coverage = returns.notna().mean()
        valid_tickers = coverage[coverage >= min_coverage].index
        removed_tickers = coverage[coverage < min_coverage].index
        returns = returns[valid_tickers]

        # Remove remaining incomplete dates
        returns = returns.dropna(axis=0)

        if returns.empty:
            raise RuntimeError("No valid aligned return observations available.")

        logger.debug(
            "Aligned returns: %d observations, %d tickers retained, "
            "%d tickers removed",
            returns.shape[0],
            returns.shape[1],
            len(removed_tickers),
        )

        return returns

    @staticmethod
    def _calculate_pca(returns: pd.DataFrame, n_components: int = 5) -> tuple[pd.DataFrame, PCA]:
        """
        Calculates assets' PCA n components from their returns
        :param returns: The assets' returns
        :param n_components: How many components to select
        :raises RuntimeError: When the given returns are empty
        :return: A dataframe with each pca component for each stock
        """
        if returns.empty:
            raise RuntimeError("Can't calculate PCA on empty returns.")

        max_components = min(returns.shape)

        if n_components > max_components:
            raise ValueError(
                f"n_components={n_components} exceeds the maximum "
                f"possible value ({max_components})."
            )

        logger.debug(
            "Calculating PCA with %d components using " "%d observations and %d stocks",
            n_components,
            returns.shape[0],
            returns.shape[1],
        )
        scaler: StandardScaler = StandardScaler()
        scaled_returns = scaler.fit_transform(returns)

        pca = PCA(n_components=n_components)
        pca.fit(scaled_returns)

        features = pd.DataFrame(
            pca.components_.T,
            index=returns.columns,
            columns=[f"PC{i + 1}" for i in range(n_components)],
        )

        features.index.name = "Ticker"

        logger.debug(
            "PCA explained variance: %.2f%%",
            pca.explained_variance_ratio_.sum() * 100,
        )

        return features, pca

    @staticmethod
    def _cluster(pca_features: pd.DataFrame, min_samples: int = 3) -> pd.Series:
        """
        Find OPTICS cluster from the pca features
        :param pca_features:   coming from _calculate_pca()
        :param min_samples: Min samples to consider a cluster
        :return: The clustered tickers
        """

        if pca_features.empty:
            raise RuntimeError("Can't cluster empty PCA features.")

        clustering = OPTICS(min_samples=min_samples, )
        labels = clustering.fit_predict(pca_features)
        clusters = pd.Series(labels, index=pca_features.index, name=Feature.OPTICS_CLUSTER)

        n_clusters = clusters[clusters != -1].nunique()
        n_noise = (clusters == -1).sum()
        logger.debug(
            "OPTICS clustering done: %d clusters, %d noise tickers",
            n_clusters,
            n_noise,
        )

        return clusters

    @staticmethod
    def _generate_candidate_pairs(clusters: pd.Series, ) -> list[tuple[str, str]]:
        """
        Generates pairs candidate. The candidates are the tickeres in the same clusters
        :param clusters: The clustered tickers
        :return: A list contiaining each candidate
        """

        candidates: list[tuple[str, str]] = []

        # Ignore noise cluster (-1)
        valid_clusters = clusters[clusters != -1]

        for cluster_id in valid_clusters.unique():
            tickers = valid_clusters[valid_clusters == cluster_id].index.tolist()

            candidates.extend(combinations(tickers, 2))

        logger.debug("Generated %d candidate pairs", len(candidates))

        return candidates

    @staticmethod
    def _validate_candidates(candidates: list[tuple[str, str]], data: pd.DataFrame, config: PairSelectionConfig) -> \
            list[PairResult]:
        """
        For each candidate, check if they are are statistically tradeable
        :param candidates: The generated candidates
        :param data: The assets' data
        :param config: The configuration to use
        :return: The statistically tradeable pairs
        """
        if Feature.LOG_PRICE not in data.columns:
            raise RuntimeError("Log prices must be calculated before cointegration testing.")

        log_prices = data[Feature.LOG_PRICE].unstack("Ticker")
        results = []

        for ticker_a, ticker_b in candidates:

            pair, valid = PairEngine._test_pair(
                ticker_a=ticker_a,
                ticker_b=ticker_b,
                log_prices=log_prices,
                config=config,
            )

            if valid:
                results.append(pair)

        logger.debug("Validation done: %d candidates", len(candidates))
        return results

    @staticmethod
    def _test_pair(ticker_a: str, ticker_b: str, log_prices: pd.DataFrame, config: PairSelectionConfig) -> tuple[
        PairResult, bool]:

        result_ab = PairEngine._engle_granger(
            y=log_prices[ticker_a],
            x=log_prices[ticker_b],
        )

        result_ba = PairEngine._engle_granger(
            y=log_prices[ticker_b],
            x=log_prices[ticker_a],
        )

        if result_ab["pvalue"] <= result_ba["pvalue"]:
            best = result_ab
            ticker_y = ticker_a
            ticker_x = ticker_b
        else:
            best = result_ba
            ticker_y = ticker_b
            ticker_x = ticker_a

        is_valid = False
        hurst = None
        half_life = None
        crossings = None

        if best["pvalue"] <= config.significance_level:
            (is_valid, hurst, half_life, crossings) = PairEngine._validate_pair(
                spread=best["spread"], config=config
            )

        result = PairResult(
            ticker_y=ticker_y,
            ticker_x=ticker_x,
            pvalue=best["pvalue"],
            test_statistic=best["test_statistic"],
            hedge_ratio=best["hedge_ratio"],
            intercept=best["intercept"],
            hurst=hurst,
            half_life=half_life,
            mean_crossings=crossings,
            spread_mean=best["spread"].mean(),
            spread_std=best["spread"].std()
        )
        return result, is_valid

    @staticmethod
    def _engle_granger(
            y: pd.Series,
            x: pd.Series,
    ) -> dict:

        # Align both series
        prices = pd.concat([y, x], axis=1).dropna()

        if len(prices) < 2:
            raise ValueError("Not enough observations for Engle-Granger test.")

        y_aligned = prices.iloc[:, 0]
        x_aligned = prices.iloc[:, 1]

        test_statistic, pvalue, _ = coint(
            y_aligned,
            x_aligned,
        )

        # Add intercept
        X = sm.add_constant(x_aligned)

        # OLS regression:
        # y = alpha + beta * x + residual
        model = sm.OLS(
            y_aligned,
            X,
        ).fit()

        intercept = model.params.iloc[0]
        hedge_ratio = model.params.iloc[1]

        spread = model.resid

        return {
            "pvalue": pvalue,
            "test_statistic": test_statistic,
            "hedge_ratio": hedge_ratio,
            "intercept": intercept,
            "spread": spread,
        }

    @staticmethod
    def _validate_pair(
            spread: pd.Series,
            config: PairSelectionConfig
    ) -> tuple[bool, float, float, float]:
        hurst, half_life, crossings = PairEngine._calculate_mean_reversion_metrics(
            spread
        )
        is_valid = (
                hurst < config.max_hurst
                and config.min_half_life < half_life < config.max_half_life
                and crossings >= config.min_crossings
        )

        return (
            is_valid,
            hurst,
            half_life,
            crossings,
        )

    @staticmethod
    def _calculate_mean_reversion_metrics(
            spread: pd.Series,
    ) -> tuple[float, float, float]:

        hurst = PairEngine._calculate_hurst(spread)

        half_life = PairEngine._calculate_half_life(spread)

        crossings = PairEngine._calculate_mean_crossings(spread)

        return (
            hurst,
            half_life,
            crossings,
        )

    @staticmethod
    def _calculate_hurst(
            spread_pd: pd.Series,
            max_lag: int = 100,
    ) -> float:

        spread = spread_pd.dropna().to_numpy(dtype=float)

        if len(spread) < 20:
            raise ValueError("Not enough observations to estimate Hurst exponent.")

        max_lag = min(
            max_lag,
            len(spread) // 2,
        )

        if max_lag <= 2:
            raise ValueError("Not enough observations to estimate Hurst exponent.")

        lags = np.arange(2, max_lag)

        variances = np.array(
            [
                np.var(
                    spread[lag:] - spread[:-lag],
                    ddof=1,
                )
                for lag in lags
            ]
        )

        # Remove invalid / zero variance observations
        valid = np.isfinite(variances) & (variances > 0)

        if valid.sum() < 2:
            raise ValueError("Unable to estimate Hurst exponent.")

        slope, _ = np.polyfit(
            np.log(lags[valid]),
            np.log(variances[valid]),
            1,
        )

        hurst = slope / 2.0

        return float(hurst)

    @staticmethod
    def _calculate_half_life(
            spread: pd.Series,
    ) -> float:

        spread = spread.dropna().astype(float)

        if len(spread) < 3:
            raise ValueError("Not enough observations to calculate half-life.")

        lagged_spread = spread.shift(1)
        delta_spread = spread.diff()

        regression_data = pd.concat(
            [
                lagged_spread.rename("lagged"),
                delta_spread.rename("delta"),
            ],
            axis=1,
        ).dropna()

        X = sm.add_constant(regression_data["lagged"])

        model = sm.OLS(
            regression_data["delta"],
            X,
        ).fit()

        beta = model.params["lagged"]

        # beta >= 0 means no estimated restoring force
        if beta >= 0 or beta <= -1:
            return np.inf

        half_life = -np.log(2) / np.log(1.0 + beta)

        return float(half_life)

    @staticmethod
    def _calculate_mean_crossings(
            spread: pd.Series,
            trading_days_per_year: int = 252,
    ) -> float:
        values = spread.dropna().to_numpy(dtype=float)

        if not np.isfinite(values).all():
            raise ValueError("Spread must be finite.")

        if len(values) < 2:
            return 0.0

        signs = np.sign(values - values.mean())
        nonzero_signs = signs[signs != 0]

        if len(nonzero_signs) < 2:
            return 0.0

        crossings = np.count_nonzero(
            nonzero_signs[1:] != nonzero_signs[:-1]
        )

        return float(crossings * trading_days_per_year / len(values))
