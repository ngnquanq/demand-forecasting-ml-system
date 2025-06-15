import pandas as pd
import pytest
from fastapi import UploadFile
from io import BytesIO
from fastapi import HTTPException
import sys
import os
from pathlib import Path
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import make_column_transformer, make_column_selector
import numpy as np

# Add the root directory to the Python path
# This is crucial for imports like src.data.data_loader and src.model.forecast_model
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your application's components
from src.data.data_loader import load_data_from_csv
from src.model.forecast_model import run_bayesian_hyperparameter_search_and_fit, train_forecaster_with_best_params
from skforecast.preprocessing import RollingFeatures # Make sure this import path is correct for your project
from src.api.main import app  
from fastapi.testclient import TestClient

END_VALIDATION = "2012-12-09 08:00:00"
STEPS_TO_PREDICT = 36 # Number of hours to forecast
N_TRIALS_FOR_TEST = 2 # Reduced for faster testing; use a higher number for actual search


@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(scope="module") 
def prepared_model_and_data(csv_file_path):
    """
    Pytest fixture that loads and preprocesses data, performs a quick
    hyperparameter search, and trains the forecasting model.
    It yields the trained model, exogenous data for prediction, and actual values.
    """
    print(f"\n[conftest.py] Preparing model and data using {csv_file_path}...") # For visibility during test run
    try:
        with csv_file_path.open("rb") as f:
            file_content = f.read()
        # Use BytesIO to simulate UploadFile for your load_data_from_csv function
        mock_upload_file = UploadFile(filename=csv_file_path.name, file=BytesIO(file_content))
        data = load_data_from_csv(mock_upload_file)
    except FileNotFoundError:
        pytest.fail(f"Test data file not found at {csv_file_path}. Please ensure it exists.")
    except HTTPException as e:
        pytest.fail(f"HTTP Error loading data: {e.detail}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred loading data: {e}")

    # Ensure the 'date_time' column is a proper datetime index for slicing
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)

    y = data["users"].copy()

    ordinal_encoder = make_column_transformer(
        (
            OrdinalEncoder(handle_unknown='use_encoded_value',
                           unknown_value=-1,
                           encoded_missing_value=-1),
            make_column_selector(dtype_exclude=np.number)
        ),
        remainder="passthrough",
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")

    exog = data.drop(columns=["users"]).copy()
    exog_features = exog.columns.to_list()

    # Instantiate your RollingFeatures class
    window_features = RollingFeatures(stats=["mean"], window_sizes=24*3)


    search_result = run_bayesian_hyperparameter_search_and_fit(
        data=data,
        end_validation=END_VALIDATION,
        exog_features=exog_features,
        window_features=window_features,
        transformer_exog=ordinal_encoder,
        n_trials=N_TRIALS_FOR_TEST,
        steps=STEPS_TO_PREDICT,
        initial_train_size=round(len(y) * 0.8),
        random_state=2025
    )

    model = train_forecaster_with_best_params(
        data=data,
        end_validation=END_VALIDATION,
        exog_features=exog_features,
        window_features=window_features,
        transformer_exog=ordinal_encoder,
        best_params=search_result["best_params"],
        best_lags=search_result["best_lags"]
    )

    end_validation_dt = pd.to_datetime(END_VALIDATION) + pd.Timedelta(hours=1)
    exog_for_prediction = data.loc[end_validation_dt:, exog_features].head(STEPS_TO_PREDICT)
    actual_values = data.loc[end_validation_dt:, "users"].head(STEPS_TO_PREDICT)

    # Yield the prepared components. Pytest will automatically tear down
    # (e.g., close files if any were opened without 'with') after tests are done.
    yield model, exog_for_prediction, actual_values
    print("[conftest.py] Model and data preparation complete. Fixture teardown (if any) will occur.")



@pytest.fixture
def csv_file_path():
    return Path(__file__).parent / "test_1.csv"

@pytest.fixture
def csv_file(csv_file_path):
    with csv_file_path.open("rb") as f:
        yield {
            "file": ("test_1.csv", f, "text/csv")
        }

