import pandas as pd
from loguru import logger
from opentelemetry import trace
from src.data.data_loader import *
from src.data.preprocessing import *
from src.data.validation import *
from src.model.forecast_model import *

tracer = trace.get_tracer("application.tracer")


def predict_future(model, data, exog_features, end_validation_dt, forecast_hours):
    with tracer.start_as_current_span("make-predictions"):
        exog_pred_start_dt = data.index[data.index > end_validation_dt].min()

        if pd.isna(exog_pred_start_dt):
            logger.error("No future exogenous data available for prediction.")
            raise ValueError("No future exogenous data available for prediction.")

        exog_pred = data.loc[exog_pred_start_dt:, exog_features].head(forecast_hours)

        if len(exog_pred) < forecast_hours:
            logger.warning(
                f"Not enough future exogenous data for {forecast_hours} steps. Predicting only {len(exog_pred)} steps."
            )

        predictions = model.predict(steps=len(exog_pred), exog=exog_pred)
        logger.info(f"Predictions made for {len(predictions)} steps.")

        return predictions, exog_pred, exog_pred.index
