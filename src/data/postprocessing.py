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


def combine_forecast_with_truth(
    predictions,
    exog_pred,
    data,
):
    with tracer.start_as_current_span("combine-results"):
        future_index = exog_pred.index

        if "users" not in data.columns:
            logger.error("Missing 'users' column in data for comparison.")
            raise ValueError("Cannot compare to 'real_users': column not found.")

        forecast_df = pd.DataFrame(
            {
                "date_time": future_index,
                "predicted_users": np.ceil(predictions).astype(int),
                "real_users": data.loc[future_index, "users"].values,
            }
        )
        forecast_df.set_index("date_time", inplace=True)

        # Combine with exogenous predictors for traceability
        forecast_df = pd.concat([forecast_df, exog_pred], axis=1)

        logger.info("Forecast results combined.")
        return forecast_df
