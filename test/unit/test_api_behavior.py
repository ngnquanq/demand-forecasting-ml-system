import os
import sys

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_loader import load_data_from_csv


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


def test_load_data_from_csv_different_datetime_formats(
    create_mock_upload_file, sample_csv_content_different_datetime_formats
):
    """Tests loading CSV with different date/time formats."""
    upload_file = create_mock_upload_file(sample_csv_content_different_datetime_formats)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert isinstance(df.index, pd.DatetimeIndex)


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


if __name__ == "__main__":
    print("Running tests...")
