from __future__ import annotations

import hashlib
import json
import logging

from datetime import datetime, date, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd
import yfinance as yf


logger = logging.getLogger(__name__)


class DataFetcher:
    CACHE_DIR = Path("./cache")
    CACHE_VERSION = 1

    # Explicitly defined for reproducibility.
    AUTO_ADJUST = True
    REPAIR = True
    PREPOST = False

    @classmethod
    def fetch(
        cls,
        tickers: Sequence[str],
        start_date: datetime | date,
        end_date: datetime | date,
        interval: str = "1d",
        cache: bool = True,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        tickers = cls._normalize_tickers(tickers)
        start_date = pd.Timestamp(start_date)
        end_date = pd.Timestamp(end_date)

        cls._validate_parameters(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
        )

        cache_params = cls._build_cache_params(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        cache_key = cls._build_cache_key(cache_params)

        data_path = cls.CACHE_DIR / f"{cache_key}.parquet"
        metadata_path = cls.CACHE_DIR / f"{cache_key}.json"

        # ------------------------------------------------------------
        # Cache
        # ------------------------------------------------------------

        if cache and not force_refresh and data_path.exists():
            logger.info("Loading market data from cache: %s", cache_key)

            data = pd.read_parquet(data_path)

            cls._validate_data(data, tickers)

            return data

        # ------------------------------------------------------------
        # Download
        # ------------------------------------------------------------

        logger.info(
            "Downloading market data for %d tickers from %s to %s",
            len(tickers),
            start_date,
            end_date,
        )

        data = yf.download(
            tickers=tickers,
            start=start_date,
            end=end_date,
            interval=interval,

            auto_adjust=cls.AUTO_ADJUST,
            repair=cls.REPAIR,
            prepost=cls.PREPOST,

            group_by="column",
            multi_level_index=True,

            threads=True,
            progress=False,
        )

        if data is None or data.empty:
            raise RuntimeError(
                "yfinance returned no data for the requested parameters."
            )

        data = (
            data
            .stack(level="Ticker", future_stack=True)
            .swaplevel()
            .sort_index()
        )

        data.index.names = ["Ticker", "Date"]
        data.columns.name = None

        # Normalize datetime representation
        ticker_index = data.index.get_level_values("Ticker")
        date_index = pd.to_datetime(
            data.index.get_level_values("Date")
        )

        data.index = pd.MultiIndex.from_arrays(
            [ticker_index, date_index],
            names=["Ticker", "Date"],
        )

        # Drop rows containing absolutely no market information
        data = data.dropna(how="all")

        cls._validate_data(data, tickers)

        # Save cache

        if cache:
            cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

            data.to_parquet(data_path)

            metadata = {
                **cache_params,
                "cache_key": cache_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "rows": len(data),
                "columns": list(data.columns),
            }

            with metadata_path.open("w", encoding="utf-8") as file:
                json.dump(metadata, file, indent=4)

        return data

    # Cache
    @classmethod
    def _build_cache_params(
        cls,
        tickers: Sequence[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        interval: str,
    ) -> dict:

        return {
            "version": cls.CACHE_VERSION,
            "tickers": list(tickers),
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "interval": interval,
            "auto_adjust": cls.AUTO_ADJUST,
            "repair": cls.REPAIR,
            "prepost": cls.PREPOST,
        }

    @staticmethod
    def _build_cache_key(params: dict) -> str:
        serialized = json.dumps(
            params,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()[:16]

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    @staticmethod
    def _normalize_tickers(
        tickers: Sequence[str],
    ) -> tuple[str, ...]:

        normalized = {
            ticker.strip().upper()
            for ticker in tickers
            if ticker.strip()
        }

        if not normalized:
            raise ValueError("At least one ticker must be provided.")

        # Sorted => ticker order does not change the cache key
        return tuple(sorted(normalized))

    @staticmethod
    def _validate_parameters(
        tickers: Sequence[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> None:

        if not tickers:
            raise ValueError("Ticker list cannot be empty.")

        if start_date >= end_date:
            raise ValueError(
                "start_date must be earlier than end_date."
            )

    @staticmethod
    def _validate_data(
        data: pd.DataFrame,
        requested_tickers: Sequence[str],
    ) -> None:

        if data.empty:
            raise RuntimeError("Market dataset is empty.")

        if not isinstance(data.index, pd.MultiIndex):
            raise RuntimeError(
                "Expected a MultiIndex DataFrame."
            )

        if data.index.names != ["Ticker", "Date"]:
            raise RuntimeError(
                "Expected index levels ['Ticker', 'Date']."
            )

        if data.index.has_duplicates:
            raise RuntimeError(
                "Duplicate (Ticker, Date) observations detected."
            )

        available_tickers = set(
            data.index.get_level_values("Ticker")
        )

        missing_tickers = (
            set(requested_tickers) - available_tickers
        )

        if missing_tickers:
            raise RuntimeError(
                "No data returned for ticker(s): "
                f"{sorted(missing_tickers)}"
            )