import os
import sys
import pandas as pd
from fastapi import HTTPException, UploadFile
import pytest
import io
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import make_column_transformer, make_column_selector
import numpy as np 


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_mae_is_larger_than_100(prepared_model_and_data):
    """
    Tests if the Mean Absolute Error (MAE) of the model's predictions
    is strictly greater than 100. (the number here is arbitrary and can be adjusted
    based on the expected performance of the model).
    """
    # The fixture provides these directly
    model, exog_for_prediction, actual_values = prepared_model_and_data

    future_predictions = model.predict(
        steps=len(actual_values),
        exog=exog_for_prediction
    )

    assert len(future_predictions) == len(actual_values), \
        "Prediction length does not match actuals length for MAE calculation."

    mae = mean_absolute_error(actual_values, future_predictions)
    print(f"\nCalculated MAE (for >100 check): {mae:.2f}")

    # This test will PASS if MAE > 100.
    assert mae > 100, f"MAE ({mae:.2f}) is NOT strictly larger than 100."


def test_mae_is_within_acceptable_range(prepared_model_and_data):
    """
    Tests if the Mean Absolute Error (MAE) is within an acceptable upper bound,
    implying reasonable model performance.
    """
    # The fixture provides these directly
    model, exog_for_prediction, actual_values = prepared_model_and_data

    future_predictions = model.predict(
        steps=len(actual_values),
        exog=exog_for_prediction
    )

    assert len(future_predictions) == len(actual_values), \
        "Prediction length does not match actuals length for MAE calculation."

    mae = mean_absolute_error(actual_values, future_predictions)
    print(f"\nCalculated MAE (for acceptable range check): {mae:.2f}")

    ACCEPTABLE_MAE_THRESHOLD = 90 
    assert mae <= ACCEPTABLE_MAE_THRESHOLD, \
        f"MAE ({mae:.2f}) is greater than the acceptable threshold of {ACCEPTABLE_MAE_THRESHOLD}. Model performance might be poor."

