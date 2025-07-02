import pandas as pd
import pytest
from sklearn.metrics import mean_absolute_error

from src.data.validation import get_validation_cutoff
from src.model.forecast_model import evaluate_forecast


def test_get_validation_cutoff_raises_when_data_insufficient():
    index = pd.date_range("2025-01-01", periods=3, freq="h", tz="UTC")
    df = pd.DataFrame(index=index)

    with pytest.raises(ValueError, match="Not enough data"):
        get_validation_cutoff(df, forecast_hours=2)


def test_evaluate_forecast_valid_case():
    index = pd.date_range("2025-01-01", periods=3, freq="h", tz="UTC")
    real = [100, 120, 110]
    pred = [98, 118, 105]

    df = pd.DataFrame(
        {
            "real_users": real,
            "predicted_users": pred,
        },
        index=index,
    )

    mae = evaluate_forecast(df)
    assert mae == mean_absolute_error(real, pred)
