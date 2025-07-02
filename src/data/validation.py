import os
import sys

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


def get_validation_cutoff(data, forecast_hours):
    with tracer.start_as_current_span("prepare-validation-window"):
        if len(data) < forecast_hours + 2:
            logger.error(
                "Not enough data for forecasting and validation after resampling."
            )
            raise ValueError(
                "Not enough data for forecasting and validation given forecast_hours."
            )

        end_validation = data.index[-forecast_hours - 1]
        logger.info(f"Validation ends at: {end_validation}")
        return end_validation


def evaluate_forecast(forecast_df):
    with tracer.start_as_current_span("evaluate") as eval_span:
        if len(forecast_df["real_users"]) != len(forecast_df["predicted_users"]):
            logger.warning(
                "Length mismatch between real_users and predicted_users for MAE calculation."
            )
            mae = None
        else:
            mae = mean_absolute_error(
                forecast_df["real_users"], forecast_df["predicted_users"]
            )

        forecast_df.index = forecast_df.index.strftime("%Y-%m-%d %H:%M:%S")
        eval_span.set_attribute("mae", mae)
        logger.info("Forecast evaluated.", mae=mae)

        return mae
