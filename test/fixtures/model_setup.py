import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import HTTPException, UploadFile
from skforecast.preprocessing import RollingFeatures
from sklearn.compose import make_column_selector, make_column_transformer
from sklearn.preprocessing import OrdinalEncoder

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data.data_loader import *
from src.model.forecast_model import (
    run_bayesian_hyperparameter_search_and_fit,
    train_forecaster_with_best_params,
)

END_VALIDATION = "2012-12-09 08:00:00"
STEPS_TO_PREDICT = 36
N_TRIALS_FOR_TEST = 2


def prepare_model_and_data(csv_file_path):
    try:
        with csv_file_path.open("rb") as f:
            file_content = f.read()
        mock_upload_file = UploadFile(
            filename=csv_file_path.name, file=BytesIO(file_content)
        )
        data = load_data_from_csv(mock_upload_file)
    except Exception as e:
        raise RuntimeError(f"Error loading CSV file: {e}") from e

    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)

    y = data["users"].copy()

    transformer_exog = make_column_transformer(
        (
            OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1,
                encoded_missing_value=-1,
            ),
            make_column_selector(dtype_exclude=np.number),
        ),
        remainder="passthrough",
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")

    exog = data.drop(columns=["users"]).copy()
    exog_features = exog.columns.tolist()
    window_features = RollingFeatures(stats=["mean"], window_sizes=24 * 3)

    search_result = run_bayesian_hyperparameter_search_and_fit(
        data=data,
        end_validation=END_VALIDATION,
        exog_features=exog_features,
        window_features=window_features,
        transformer_exog=transformer_exog,
        n_trials=N_TRIALS_FOR_TEST,
        steps=STEPS_TO_PREDICT,
        initial_train_size=round(len(y) * 0.8),
        random_state=2025,
    )

    model = train_forecaster_with_best_params(
        data=data,
        end_validation=END_VALIDATION,
        exog_features=exog_features,
        window_features=window_features,
        transformer_exog=transformer_exog,
        best_params=search_result["best_params"],
        best_lags=search_result["best_lags"],
    )

    end_validation_dt = pd.to_datetime(END_VALIDATION) + pd.Timedelta(hours=1)
    exog_pred = data.loc[end_validation_dt:, exog_features].head(STEPS_TO_PREDICT)
    actual = data.loc[end_validation_dt:, "users"].head(STEPS_TO_PREDICT)

    return model, exog_pred, actual
