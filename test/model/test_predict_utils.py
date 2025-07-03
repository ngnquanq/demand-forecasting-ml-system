import pandas as pd
import pytest

from src.model.predict_utils import predict_future


def test_predict_future_success(
    fake_forecast_model, mock_data_with_users, mock_predictions
):
    end_validation_dt = mock_data_with_users.index[5]
    forecast_hours = 3
    exog_features = ["temp", "humidity"]

    preds, exog_pred, index_pred = predict_future(
        model=fake_forecast_model,
        data=mock_data_with_users,
        exog_features=exog_features,
        end_validation_dt=end_validation_dt,
        forecast_hours=forecast_hours,
    )

    assert isinstance(preds, pd.Series)
    assert len(preds) == forecast_hours
    assert exog_pred.shape == (forecast_hours, 2)
    pd.testing.assert_index_equal(index_pred, exog_pred.index)
    pd.testing.assert_series_equal(preds, mock_predictions[:forecast_hours])


def test_predict_future_no_future_data(fake_forecast_model, mock_data_with_users):
    end_validation_dt = mock_data_with_users.index[-1]  # No future data after this
    exog_features = ["temp", "humidity"]
    forecast_hours = 3

    with pytest.raises(ValueError, match="No future exogenous data available"):
        predict_future(
            model=fake_forecast_model,
            data=mock_data_with_users,
            exog_features=exog_features,
            end_validation_dt=end_validation_dt,
            forecast_hours=forecast_hours,
        )
