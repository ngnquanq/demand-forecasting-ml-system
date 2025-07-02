# test/conftest.py
import io
import os
from datetime import datetime, timedelta, tzinfo
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from fixtures.model_setup import prepare_model_and_data
from psycopg2 import OperationalError

from src.api.main import app

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_NAME = "test_db"
DEFAULT_DB_USER = "test_user"
DEFAULT_DB_PASSWORD = "test_password"
DEFAULT_SCHEMA_NAME = "public"
DEFAULT_TABLE_NAME = "data_table"
DEFAULT_TIME_COLUMN = "timestamp"


class FixedOffset(tzinfo):
    def __init__(self, offset_hours):
        self._offset = timedelta(hours=offset_hours)
        self._name = (
            f"+{offset_hours:02d}00" if offset_hours >= 0 else f"{offset_hours:03d}00"
        )

    def utcoffset(self, dt):
        return self._offset

    def tzname(self, dt):
        return self._name

    def dst(self, dt):
        return timedelta(0)


@pytest.fixture(
    scope="module", autouse=True
)  # Add autouse=True to apply globally for module
def set_test_env():
    """Sets the environment variable to 'test' for the duration of the module tests."""
    original_env = os.environ.get("ENV")
    os.environ["ENV"] = "test"
    yield
    if original_env is not None:
        os.environ["ENV"] = original_env
    else:
        del os.environ["ENV"]


@pytest.fixture(
    scope="module"
)  # Use module scope for efficiency, as the app is immutable for tests
def client():
    """
    Provides a TestClient for the FastAPI application.
    This fixture will be available to all test files.
    """
    with TestClient(app=app) as c:
        yield c


@pytest.fixture
def api_mock_get_min_max_time_success():
    """
    Mocks get_min_max_time_from_db to return successful, UTC-aware Timestamps.
    These are the expected UTC conversions from your example data (+0700).
    """
    min_time = pd.Timestamp(
        "2012-08-31 17:00:00+0000", tz="UTC"
    )  # Corresponds to 2012-09-01 00:00:00+0700
    max_time = pd.Timestamp(
        "2012-12-11 04:00:00+0000", tz="UTC"
    )  # Corresponds to 2012-12-11 11:00:00+0700
    with patch(
        "src.api.main.get_min_max_time_from_db", return_value=(min_time, max_time)
    ) as mock_func:
        yield mock_func


@pytest.fixture
def api_mock_get_min_max_time_no_data():
    """
    Mocks get_min_max_time_from_db to return (None, None) for no data.
    """
    with patch(
        "src.api.main.get_min_max_time_from_db", return_value=(None, None)
    ) as mock_func:
        yield mock_func


@pytest.fixture
def api_mock_get_min_max_time_error():
    """
    Mocks get_min_max_time_from_db to raise an exception, simulating a DB error.
    """
    with patch(
        "src.api.main.get_min_max_time_from_db",
        side_effect=OperationalError("Mock DB Error"),
    ) as mock_func:
        yield mock_func


@pytest.fixture
def api_mock_logger():
    """
    Mocks the logger used within src.api.main.
    """
    with patch("src.api.main.logger") as mock_log:
        yield mock_log


@pytest.fixture
def api_mock_tracer():
    """
    Mocks the OpenTelemetry tracer and its span context manager.
    """
    mock_span = MagicMock()
    mock_start_as_current_span = MagicMock()
    # Configure the mock context manager to return the mock_span
    mock_start_as_current_span.__enter__.return_value = mock_span
    mock_start_as_current_span.__exit__.return_value = None

    # Patch the start_as_current_span method itself
    with patch(
        "src.api.main.tracer.start_as_current_span",
        return_value=mock_start_as_current_span,
    ) as mock_tracer_obj:
        yield mock_tracer_obj, mock_span  # Yield both for asserting calls on tracer and span


@pytest.fixture
def mock_get_data_as_dataframe_filtered():
    """
    Mocks the get_data_as_dataframe_filtered function to return a predefined DataFrame
    that mimics the structure and content shown in the provided images.
    This mock DataFrame will be sufficiently long to cover training, validation,
    and a future prediction period.
    """
    num_records = 600  # Sufficiently large number of hours

    start_dt_mock = pd.to_datetime("2012-09-01 00:00:00+0700")
    date_time_index = pd.date_range(
        start=start_dt_mock, periods=num_records, freq="h", tz="Asia/Ho_Chi_Minh"
    )

    # Create dummy data for each column
    users = np.random.randint(10, 200, size=num_records)
    holiday = np.zeros(num_records, dtype=int)
    weather = np.random.choice(["clear", "cloudy", "rainy"], size=num_records)
    temp = np.random.uniform(20.0, 35.0, size=num_records).round(2)
    atemp = np.random.uniform(25.0, 40.0, size=num_records).round(2)
    hum = np.random.randint(50, 90, size=num_records)
    windspeed = np.random.uniform(0.0, 15.0, size=num_records).round(4)

    data_dict = {
        "users": users,
        "holiday": holiday,
        "weather": weather,
        "temp": temp,
        "atemp": atemp,
        "hum": hum,
        "windspeed": windspeed,
    }

    df = pd.DataFrame(data_dict, index=date_time_index)

    df["users"] = df["users"].astype(int)
    df["holiday"] = df["holiday"].astype(int)
    df["hum"] = df["hum"].astype(int)

    # Now, mock the return value.
    mock_func = MagicMock()
    mock_func.return_value = df  # Assign the actual DataFrame here

    yield mock_func


@pytest.fixture
def mock_rolling_features():
    """Mocks the RollingFeatures class."""
    with patch("src.api.main.RollingFeatures") as mock:
        yield mock


@pytest.fixture
def mock_create_encoder():
    """Mocks the create_encoder function."""
    with patch("src.api.main.create_encoder") as mock:
        yield mock


@pytest.fixture
def mock_run_bayesian_hyperparameter_search_and_fit():
    """Mocks the hyperparameter tuning function."""
    with patch("src.api.main.run_bayesian_hyperparameter_search_and_fit") as mock:
        yield mock


@pytest.fixture
def mock_train_forecaster_with_best_params():
    """Mocks the model training function."""
    with patch("src.api.main.train_forecaster_with_best_params") as mock:
        yield mock


@pytest.fixture
def mock_mean_absolute_error():
    """Mocks the mean_absolute_error function."""
    with patch("src.api.main.mean_absolute_error") as mock:
        yield mock


@pytest.fixture
def mock_np_ceil():
    """Mocks numpy.ceil to ensure it's called as expected."""
    with patch("numpy.ceil") as mock:
        mock.side_effect = np.ceil  # Still call original np.ceil logic
        yield mock


@pytest.fixture
def mock_main_pd_to_datetime_error():
    """
    Mocks pandas.to_datetime when used directly in src.api.main (e.g., for parsing start_time/stop_time query params).
    This simulates an invalid timestamp format for the DB endpoint.
    """
    with patch(
        "src.api.main.pd.to_datetime",
        side_effect=ValueError("Invalid timestamp string for endpoint"),
    ) as mock_func:
        yield mock_func


@pytest.fixture
def mock_forecast_with_tuning_db_success():
    """
    Mocks src.api.main.forecast_with_tuning_db for success.
    """
    mock_df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-01 00:00:00+00", "2024-01-01 01:00:00+00"], utc=True
            ),
            "prediction": [100.0, 105.0],
        }
    ).set_index("timestamp")
    mock_mae = 5.2
    with patch(
        "src.api.main.forecast_with_tuning_db", return_value=(mock_df, mock_mae)
    ) as mock_func:
        yield mock_func


@pytest.fixture
def mock_forecast_with_tuning_db_error():
    """
    Mocks src.api.main.forecast_with_tuning_db to raise an exception.
    """
    with patch(
        "src.api.main.forecast_with_tuning_db",
        side_effect=ValueError("Simulated DB forecast error"),
    ) as mock_func:
        yield mock_func


@pytest.fixture
def tz_plus_7_fixture():
    return FixedOffset(7)


@pytest.fixture(autouse=True)
def clean_env():
    original_env = os.environ.copy()
    keys_to_clear = [
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_SCHEMA",
        "DB_TABLE",
        "TIME_COLUMN",
    ]
    for key in keys_to_clear:
        if key in os.environ:
            del os.environ[key]
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_db_connection_params():
    # Patch target updated to 'src.data.data_loader.get_db_connection_params'
    with patch("src.data.data_loader.get_db_connection_params") as mock_get_params:
        mock_get_params.return_value = (
            "mock_host",
            "mock_db",
            "mock_user",
            "mock_pass",
            "mock_schema",
            "mock_table",
            "date_time",
        )
        yield mock_get_params


@pytest.fixture
def mock_psycopg2_success(tz_plus_7_fixture):
    mock_min_time_raw = datetime(2012, 9, 1, 0, 0, 0, tzinfo=tz_plus_7_fixture)
    mock_max_time_raw = datetime(2012, 12, 11, 11, 0, 0, tzinfo=tz_plus_7_fixture)

    # Patch target updated to 'src.data.data_loader.psycopg2.connect'
    with patch("src.data.data_loader.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (mock_min_time_raw, mock_max_time_raw)

        yield mock_connect, mock_conn, mock_cursor


@pytest.fixture
def mock_psycopg2_no_data():
    # Patch target updated to 'src.data.data_loader.psycopg2.connect'
    with patch("src.data.data_loader.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None, None)

        yield mock_connect, mock_conn, mock_cursor


@pytest.fixture
def mock_psycopg2_fetchall_no_data():  # <--- Ensure it is named exactly this
    mock_column_names = [
        ("date_time", None, None, None, None, None, None),
        ("users", None, None, None, None, None, None),
        ("holiday", None, None, None, None, None, None),
        ("weather", None, None, None, None, None, None),
        ("temp", None, None, None, None, None, None),
        ("atemp", None, None, None, None, None, None),
        ("hum", None, None, None, None, None, None),
        ("windspeed", None, None, None, None, None, None),
    ]

    with patch("src.data.data_loader.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []  # Empty list for no data
        mock_cursor.description = mock_column_names

        yield mock_connect, mock_conn, mock_cursor


# Ensure you still have this for fetchone no data, which is separate:
@pytest.fixture
def mock_psycopg2_fetchone_no_data():
    with patch("src.data.data_loader.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None, None)
        yield mock_connect, mock_conn, mock_cursor


@pytest.fixture
def mock_psycopg2_fetchall_success(tz_plus_7_fixture):
    mock_data = [
        (
            datetime(2012, 9, 1, 0, 0, 0, tzinfo=tz_plus_7_fixture),
            168,
            0,
            "clear",
            30.34,
            34.09,
            62,
            7.0015,
        ),
        (
            datetime(2012, 9, 1, 1, 0, 0, tzinfo=tz_plus_7_fixture),
            79,
            0,
            "clear",
            29.52,
            34.85,
            74,
            8.9981,
        ),
        (
            datetime(2012, 9, 1, 2, 0, 0, tzinfo=tz_plus_7_fixture),
            69,
            0,
            "clear",
            28.7,
            32.575,
            70,
            11.0014,
        ),
        (
            datetime(2012, 9, 1, 3, 0, 0, tzinfo=tz_plus_7_fixture),
            35,
            0,
            "clear",
            28.7,
            32.575,
            70,
            7.0015,
        ),
        (
            datetime(2012, 9, 1, 4, 0, 0, tzinfo=tz_plus_7_fixture),
            12,
            0,
            "clear",
            28.7,
            32.575,
            70,
            0.0,
        ),
    ]
    # The description only needs the first element (column name) for pandas to pick it up
    mock_column_names = [
        ("date_time", None, None, None, None, None, None),
        ("users", None, None, None, None, None, None),
        ("holiday", None, None, None, None, None, None),
        ("weather", None, None, None, None, None, None),
        ("temp", None, None, None, None, None, None),
        ("atemp", None, None, None, None, None, None),
        ("hum", None, None, None, None, None, None),
        ("windspeed", None, None, None, None, None, None),
    ]

    with patch("src.data.data_loader.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = mock_data
        mock_cursor.description = mock_column_names

        yield mock_connect, mock_conn, mock_cursor, mock_data, mock_column_names


@pytest.fixture
def mock_psycopg2_error():
    # Patch target updated to 'src.data.data_loader.psycopg2.connect'
    with patch("src.data.data_loader.psycopg2.connect") as mock_connect:
        mock_connect.side_effect = Exception("Mock DB Connection Error")
        yield mock_connect


@pytest.fixture
def mock_pd_to_datetime_with_expected_return(tz_plus_7_fixture):
    expected_min_pd_timestamp = pd.Timestamp("2012-08-31 17:00:00+0000", tz="UTC")
    expected_max_pd_timestamp = pd.Timestamp("2012-12-11 04:00:00+0000", tz="UTC")

    # Patch target updated to 'src.data.data_loader.pd.to_datetime'
    with patch("src.data.data_loader.pd.to_datetime") as mock_to_datetime:

        def custom_to_datetime_side_effect(ts_raw, utc):
            if ts_raw == datetime(2012, 9, 1, 0, 0, 0, tzinfo=tz_plus_7_fixture):
                return expected_min_pd_timestamp
            elif ts_raw == datetime(2012, 12, 11, 11, 0, 0, tzinfo=tz_plus_7_fixture):
                return expected_max_pd_timestamp
            else:
                return pd.to_datetime(ts_raw, utc=utc)

        mock_to_datetime.side_effect = custom_to_datetime_side_effect
        yield mock_to_datetime


@pytest.fixture
def mock_logger():
    # Patch target updated to 'src.data.data_loader.logger'
    with patch("src.data.data_loader.logger") as mock_log:
        yield mock_log


@pytest.fixture
def csv_file_path() -> Path:
    return Path(__file__).parent / "test_data.csv"


@pytest.fixture
def csv_file(csv_file_path):
    with csv_file_path.open("rb") as f:
        yield {"file": ("test_data.csv", f, "text/csv")}


@pytest.fixture
def create_mock_upload_file():
    def _create_file(content: bytes, filename: str = "test_data.csv") -> UploadFile:
        return UploadFile(file=BytesIO(content), filename=filename)

    return _create_file


@pytest.fixture
def prepared_model_and_data(csv_file_path):
    yield prepare_model_and_data(csv_file_path)


@pytest.fixture
def sample_csv_content_success():
    """Provides valid CSV content for successful loading tests."""
    return (
        b"date_time,users,holiday,weather,temp,atemp,hum,windspeed\n"
        b"2012-09-01 00:00:00,168,0,clear,30.34,34.09,62,7.0015\n"
        b"2012-09-01 01:00:00,79,0,clear,29.52,34.85,74,8.9981"
    )


@pytest.fixture
def sample_csv_content_different_datetime_formats():
    """Provides CSV content with different date/time formats."""
    return (
        b"date_time,users\n"
        b"2012/09/01 00:00:00,168\n"
        b"09/01/2012 01:00:00,79\n"
        b"2012-09-01T02:00:00,69"
    )


@pytest.fixture
def sample_csv_content_invalid_datetime_format():
    """Provides CSV content with invalid date/time formats."""
    return b"date_time,users\n" b"invalid-date,168\n" b"another-invalid,79"


@pytest.fixture
def sample_csv_content_missing_values():
    """Provides CSV content with missing values."""
    return (
        b"date_time,users,temp\n"
        b"2012-09-01 00:00:00,168,\n"
        b"2012-09-01 01:00:00,,29.52\n"
        b"2012-09-01 02:00:00,69,30.0"
    )


@pytest.fixture
def sample_csv_content_empty_strings():
    """Provides CSV content with empty strings."""
    return b"date_time,weather\n" b"2012-09-01 00:00:00,\n" b"2012-09-01 01:00:00,clear"


@pytest.fixture
def dataframe_from_csv(sample_csv_content_success):
    """Load the sample CSV into a pandas DataFrame."""
    csv_io = io.BytesIO(sample_csv_content_success)
    df = pd.read_csv(
        csv_io, parse_dates=["date_time"], index_col="date_time", encoding="utf-8"
    )
    df.index = pd.to_datetime(df.index, utc=True)  # ensure timezone awareness
    return df


@pytest.fixture
def mock_exog_pred():
    index = pd.date_range("2025-01-01 00:00", periods=3, freq="h", tz="UTC")
    return pd.DataFrame(
        {"temp": [22.5, 23.1, 24.0], "humidity": [60, 58, 59]}, index=index
    )


@pytest.fixture
def mock_predictions():
    return pd.Series([100.4, 150.2, 130.6])


@pytest.fixture
def mock_data_with_users():
    index = pd.date_range("2025-01-01 00:00", periods=10, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "users": [80, 90, 100, 110, 120, 130, 140, 150, 160, 170],
            "temp": np.random.rand(10),
            "humidity": np.random.rand(10),
        },
        index=index,
    )


@pytest.fixture
def fake_forecast_model(mock_predictions):
    class FakeModel:
        def predict(self, steps, exog=None):
            assert exog is not None
            return mock_predictions[:steps]

    return FakeModel()


@pytest.fixture
def mock_predict_future():
    with patch("src.model.forecast_model.predict_future") as mock:
        mock_predictions = pd.Series(
            [100.0, 110.0, 120.0],
            index=pd.date_range("2025-01-01", periods=3, freq="H", tz="UTC"),
        )
        mock_exog = pd.DataFrame(
            {"temp": [23, 24, 25], "humidity": [50, 55, 60]},
            index=mock_predictions.index,
        )
        mock.return_value = (mock_predictions, mock_exog, mock_predictions.index)
        yield mock


@pytest.fixture
def mock_combine_forecast_with_truth():
    with patch("src.model.forecast_model.combine_forecast_with_truth") as mock:
        mock_df = pd.DataFrame(
            {"real_users": [100, 110, 120], "predicted_users": [98, 111, 119]},
            index=pd.date_range("2025-01-01", periods=3, freq="H", tz="UTC"),
        )
        mock.return_value = mock_df
        yield mock
