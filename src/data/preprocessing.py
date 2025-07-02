import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from fastapi import UploadFile
from lightgbm import LGBMRegressor
from opentelemetry import trace
from optuna.trial import Trial
from skforecast.model_selection import (
    TimeSeriesFold,
    bayesian_search_forecaster,
)
from skforecast.preprocessing import RollingFeatures
from skforecast.recursive import ForecasterRecursive

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_loader import *
from src.model.forecast_model import *

tracer = trace.get_tracer("application.tracer")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")  # WARNING: Insecure for prod
SCHEMA_NAME = os.getenv("DB_SCHEMA", "application")
TABLE_NAME = os.getenv("DB_TABLE", "feature")
TIME_COLUMN = "date_time"


def prepare_time_series_data(data):
    with tracer.start_as_current_span("prepare-time-series-index"):
        # 1. Ensure index is a DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            logger.warning(
                "DataFrame index is not DatetimeIndex. Attempting conversion."
            )
            data.index = pd.to_datetime(data.index, utc=True)

        # 2. Sort the index
        data = data.sort_index()

        # 3. Handle duplicates
        if not data.index.is_unique:
            logger.warning("Duplicate timestamps found. Dropping duplicates.")
            data = data[~data.index.duplicated(keep="first")]

        # 4. Resample to full hourly index
        full_hourly_index = pd.date_range(
            start=data.index.min(), end=data.index.max(), freq="h", tz="UTC"
        )
        data = data.reindex(full_hourly_index)

        # 5. Fill missing values
        if "users" in data.columns:
            data["users"] = data["users"].fillna(0)

        for col in data.columns:
            if col != "users":
                data[col] = data[col].fillna(method="ffill")

        data = data.fillna(method="bfill")

        # 6. Infer frequency
        try:
            data.index.freq = pd.infer_freq(data.index)
            if data.index.freq != "h":
                logger.warning(
                    f"Inferred frequency {data.index.freq} is not 'h'. Setting manually."
                )
                data.index.freq = "h"
        except ValueError:
            logger.error("Could not infer frequency. Setting manually to 'h'.")
            data.index.freq = "h"

        return data


def extract_target_and_exog(data):
    with tracer.start_as_current_span("extract-features") as span:
        if "users" not in data.columns:
            logger.error("Missing 'users' column in loaded data.")
            raise ValueError(
                "The 'users' column is required but not found in the data."
            )

        y = data["users"].copy()
        exog = data.drop(columns=["users"]).copy()
        exog_features = exog.columns.to_list()

        span.set_attribute("num_features", len(exog_features))
        logger.info(f"Extracted {len(exog_features)} exogenous features.")

        return y, exog, exog_features
