import logging

import numpy as np
import pandas as pd

from data.columns import Column, Feature

logger = logging.getLogger(__name__)


class FeatureEngine:

    @staticmethod
    def add_features(data: pd.DataFrame) -> None:
        """
        Adds features to the given data frame
        Pre: Valid data order chronologically
        :param data: The source data
        :return: None
        """
        logger.info("Adding features to the dataset")
        
        if not data.index.is_monotonic_increasing:
            raise ValueError("Data must be sorted by Ticker and Date.")

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
