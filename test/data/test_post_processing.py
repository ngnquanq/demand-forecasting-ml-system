import numpy as np
import pandas as pd
import pytest

from src.data.postprocessing import combine_forecast_with_truth


def test_combine_forecast_with_truth_normal(
    mock_predictions, mock_exog_pred, mock_data_with_users
):
    result = combine_forecast_with_truth(
        mock_predictions, mock_exog_pred, mock_data_with_users
    )

    assert isinstance(result, pd.DataFrame)
    assert "predicted_users" in result.columns
    assert "real_users" in result.columns
    assert "temp" in result.columns
    assert "humidity" in result.columns

    assert result.shape[0] == 3


def test_combine_forecast_with_truth_with_numpy(mock_exog_pred, mock_data_with_users):
    predictions = np.array([98.9, 87.1, 110.2])
    result = combine_forecast_with_truth(
        predictions, mock_exog_pred, mock_data_with_users
    )

    assert all(result["predicted_users"] == np.ceil(predictions).astype(int))


def test_combine_forecast_with_truth_missing_users_column(mock_exog_pred):
    index = pd.date_range("2025-01-01 00:00", periods=5, freq="h", tz="UTC")
    bad_data = pd.DataFrame({"temp": [22.0, 23.0, 24.0, 25.0, 26.0]}, index=index)

    predictions = np.array([1, 2, 3])

    with pytest.raises(ValueError, match="real_users"):
        combine_forecast_with_truth(predictions, mock_exog_pred, bad_data)
