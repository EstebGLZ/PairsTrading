import logging

import numpy as np
import pandas as pd

from data.columns import Column, Feature, PRICE_COLUMNS


logger = logging.getLogger(__name__)


class FeatureEngine:

    @staticmethod
    def add_features(data: pd.DataFrame) -> None:
        logger.info("Adding features to the dataset")
        if data.empty:
            raise RuntimeError(
                "Can't add features to an empty dataframe. "
                "Make sure to fetch market data before calling this method."
            )

        missing_columns = [
            column
            for column in PRICE_COLUMNS
            if column not in data.columns
        ]

        if missing_columns:
            raise RuntimeError(
                f"Missing required columns: {missing_columns}"
            )

        logger.info("Calculating daily log returns")

        data[Feature.DAILY_LOG_RETURNS] = (
            data.groupby(level="Ticker")[Column.CLOSE]
            .transform(
                lambda close: np.log(
                    close / close.shift(1)
                )
            )
        )
        data[Feature.LOG_PRICE] = np.log(
            data[Column.CLOSE]
        )