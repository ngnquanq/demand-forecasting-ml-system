import os
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import HTTPException

from src.data.data_loader import (
    get_data_as_dataframe_filtered,
    get_db_connection_params,
    get_min_max_time_from_db,
    load_data_from_csv,
)
from src.data.preprocessing import extract_target_and_exog, prepare_time_series_data

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_NAME = "postgres"
DEFAULT_DB_USER = "postgres"
DEFAULT_DB_PASSWORD = "password"
DEFAULT_SCHEMA_NAME = "application"
DEFAULT_TABLE_NAME = "feature"
DEFAULT_TIME_COLUMN = "date_time"


def test_load_data_from_csv_success(
    create_mock_upload_file, sample_csv_content_success
):
    """Tests successful loading of a valid CSV file."""
    upload_file = create_mock_upload_file(sample_csv_content_success)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == [
        "users",
        "holiday",
        "weather",
        "temp",
        "atemp",
        "hum",
        "windspeed",
    ]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index[0] == pd.to_datetime("2012-09-01 00:00:00")
    assert df["users"].tolist() == [168.0, 79.0]
    assert df["weather"].tolist() == ["clear", "clear"]


def test_prepare_time_series_data_with_real_csv(dataframe_from_csv):
    df_prepared = prepare_time_series_data(dataframe_from_csv)

    assert isinstance(df_prepared, pd.DataFrame)
    assert df_prepared.index.freq is not None
    assert not df_prepared.isnull().any().any()  # no missing values
    assert "users" in df_prepared.columns
    assert df_prepared.index.freqstr == "h"  # Ensure hourly resampling


def test_extract_target_and_exog_with_real_csv(dataframe_from_csv):
    df_prepared = prepare_time_series_data(dataframe_from_csv)
    y, exog, exog_features = extract_target_and_exog(df_prepared)

    assert isinstance(y, pd.Series)
    assert isinstance(exog, pd.DataFrame)
    assert "users" not in exog.columns
    assert set(exog_features) == set(exog.columns)
    assert len(y) == len(exog)  # aligned


def test_load_data_from_csv_invalid_datetime_format(
    create_mock_upload_file, sample_csv_content_invalid_datetime_format
):
    """Tests loading CSV with invalid date/time formats."""
    upload_file = create_mock_upload_file(sample_csv_content_invalid_datetime_format)
    with pytest.raises(HTTPException) as excinfo:
        load_data_from_csv(upload_file)
    assert excinfo.value.status_code == 400
    assert "Error parsing date_time column" in excinfo.value.detail


def test_load_data_from_csv_missing_values(
    create_mock_upload_file, sample_csv_content_missing_values
):
    """Tests loading CSV with missing values."""
    upload_file = create_mock_upload_file(sample_csv_content_missing_values)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert pd.isna(df["users"][1])
    assert pd.isna(df["temp"][0])


def test_load_data_from_csv_empty_strings(
    create_mock_upload_file, sample_csv_content_empty_strings
):
    """Tests loading CSV with empty strings."""
    upload_file = create_mock_upload_file(sample_csv_content_empty_strings)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert pd.isna(df["weather"][0])
    assert df["weather"][1] == "clear"


def test_default_values():
    """
    Test that the function returns default values when no environment variables
    are set. The clean_env fixture (from conftest.py) ensures this state.
    """
    host, database, user, password, schema_name, table_name, time_column = (
        get_db_connection_params()
    )

    assert host == DEFAULT_DB_HOST
    assert database == DEFAULT_DB_NAME
    assert user == DEFAULT_DB_USER
    assert password == DEFAULT_DB_PASSWORD
    assert schema_name == DEFAULT_SCHEMA_NAME
    assert table_name == DEFAULT_TABLE_NAME
    assert time_column == DEFAULT_TIME_COLUMN


def test_all_env_variables_set():
    """
    Test that the function correctly retrieves values from environment
    variables when all are set.
    """
    mock_env = {
        "DB_HOST": "my_host",
        "DB_NAME": "my_database",
        "DB_USER": "my_user",
        "DB_PASSWORD": "my_password",
        "DB_SCHEMA": "my_schema",
        "DB_TABLE": "my_table",
        "TIME_COLUMN": "updated_at",
    }
    with patch.dict(os.environ, mock_env):
        host, database, user, password, schema_name, table_name, time_column = (
            get_db_connection_params()
        )

        assert host == "my_host"
        assert database == "my_database"
        assert user == "my_user"
        assert password == "my_password"
        assert schema_name == "my_schema"
        assert table_name == "my_table"
        assert time_column == "updated_at"


def test_get_min_max_time_from_db_success(
    mock_db_connection_params,
    mock_psycopg2_success,
    mock_pd_to_datetime_with_expected_return,
    mock_logger,
    tz_plus_7_fixture,
):
    min_time, max_time = get_min_max_time_from_db()

    mock_db_connection_params.assert_called_once()
    mock_psycopg2_success[0].assert_called_once_with(
        user="mock_user",
        password="mock_pass",
        host="mock_host",
        port="5432",
        database="mock_db",
    )

    # Make sure to include data types in the SQL queries.
    expected_sql = (
        'SELECT MIN("date_time"), MAX("date_time") FROM "mock_schema"."mock_table";'
    )
    mock_psycopg2_success[2].execute.assert_called_once_with(expected_sql)
    mock_psycopg2_success[2].fetchone.assert_called_once()

    assert mock_pd_to_datetime_with_expected_return.call_count == 2

    mock_pd_to_datetime_with_expected_return.assert_any_call(
        datetime(2012, 9, 1, 0, 0, 0, tzinfo=tz_plus_7_fixture), utc=True
    )
    mock_pd_to_datetime_with_expected_return.assert_any_call(
        datetime(2012, 12, 11, 11, 0, 0, tzinfo=tz_plus_7_fixture), utc=True
    )

    expected_min_time_pd = pd.Timestamp("2012-08-31 17:00:00+0000", tz="UTC")
    expected_max_time_pd = pd.Timestamp("2012-12-11 04:00:00+0000", tz="UTC")
    assert min_time == expected_min_time_pd
    assert max_time == expected_max_time_pd

    mock_psycopg2_success[1].close.assert_called_once()
    mock_logger.info.assert_any_call(
        "Successfully connected to PostgreSQL for min/max time retrieval."
    )
    mock_logger.info.assert_any_call(
        f"Retrieved min_time: {expected_min_time_pd}, max_time: {expected_max_time_pd}"
    )


def test_get_min_max_time_from_db_no_data(
    mock_db_connection_params, mock_psycopg2_no_data, mock_logger
):
    min_time, max_time = get_min_max_time_from_db()

    assert min_time is None
    assert max_time is None

    mock_psycopg2_no_data[2].execute.assert_called_once()
    mock_psycopg2_no_data[2].fetchone.assert_called_once()

    mock_logger.warning.assert_any_call(
        "No min/max time values found in mock_schema.mock_table."
    )
    mock_psycopg2_no_data[1].close.assert_called_once()


def test_get_data_as_dataframe_filtered_success_no_time_range(
    mock_db_connection_params, mock_psycopg2_fetchall_success, mock_logger
):
    host, db, user, pw, schema, table, time_col = mock_db_connection_params.return_value
    df = get_data_as_dataframe_filtered(host, db, user, pw, schema, table)

    mock_psycopg2_fetchall_success[0].assert_called_once_with(
        user=user, password=pw, host=host, port="5432", database=db
    )

    expected_sql = f'SELECT * FROM "{schema}"."{table}";'
    mock_psycopg2_fetchall_success[2].execute.assert_called_once_with(
        expected_sql, ()
    )  # Empty tuple for params

    assert not df.empty
    assert len(df) == 5  # Now 5 rows based on provided data
    assert df.index.name == time_col
    assert df.index.dtype == "datetime64[ns, UTC]"  # Ensure UTC

    # Define expected columns based on your image
    expected_df_columns = [
        "users",
        "holiday",
        "weather",
        "temp",
        "atemp",
        "hum",
        "windspeed",
    ]
    assert list(df.columns) == expected_df_columns

    # Calculate expected UTC timestamps based on your +0700 input data
    expected_df_index = [
        pd.Timestamp("2012-08-31 17:00:00+0000", tz="UTC"),  # 2012-09-01 00:00:00 +0700
        pd.Timestamp("2012-08-31 18:00:00+0000", tz="UTC"),  # 2012-09-01 01:00:00 +0700
        pd.Timestamp("2012-08-31 19:00:00+0000", tz="UTC"),  # 2012-09-01 02:00:00 +0700
        pd.Timestamp("2012-08-31 20:00:00+0000", tz="UTC"),  # 2012-09-01 03:00:00 +0700
        pd.Timestamp("2012-08-31 21:00:00+0000", tz="UTC"),  # 2012-09-01 04:00:00 +0700
    ]

    # Define expected data for each column based on your image
    expected_df_data = {
        "users": [168, 79, 69, 35, 12],
        "holiday": [0, 0, 0, 0, 0],
        "weather": ["clear", "clear", "clear", "clear", "clear"],
        "temp": [30.34, 29.52, 28.7, 28.7, 28.7],
        "atemp": [34.09, 34.85, 32.575, 32.575, 32.575],
        "hum": [62, 74, 70, 70, 70],
        "windspeed": [7.0015, 8.9981, 11.0014, 7.0015, 0.0],
    }

    expected_df = pd.DataFrame(
        expected_df_data, index=pd.to_datetime(expected_df_index)
    )
    expected_df.index.name = time_col

    pd.testing.assert_frame_equal(df, expected_df)

    mock_logger.info.assert_any_call("Successfully connected to PostgreSQL.")
    mock_logger.info.assert_any_call(
        f"Successfully retrieved {len(df)} rows and converted to DataFrame."
    )
    mock_psycopg2_fetchall_success[1].close.assert_called_once()


def test_get_data_as_dataframe_filtered_no_data(
    mock_db_connection_params, mock_psycopg2_fetchall_no_data, mock_logger
):
    host, db, user, pw, schema, table, time_col = mock_db_connection_params.return_value
    df = get_data_as_dataframe_filtered(host, db, user, pw, schema, table)

    mock_psycopg2_fetchall_no_data[0].assert_called_once()
    mock_psycopg2_fetchall_no_data[2].execute.assert_called_once()
    mock_psycopg2_fetchall_no_data[2].fetchall.assert_called_once()

    assert df.empty
    # Assert specific columns are present, even if no data
    expected_empty_df_columns = [
        "date_time",
        "users",
        "holiday",
        "weather",
        "temp",
        "atemp",
        "hum",
        "windspeed",
    ]
    assert list(df.columns) == expected_empty_df_columns

    mock_logger.warning.assert_any_call(
        f"No data retrieved from {schema}.{table} for the specified time range."
    )
    mock_psycopg2_fetchall_no_data[1].close.assert_called_once()
