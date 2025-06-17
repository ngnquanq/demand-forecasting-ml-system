import os 
import sys 
from unittest.mock import MagicMock, patch
import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

# Add the root dicretory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_loader import load_data_from_csv


def test_load_data_from_csv_success(create_mock_upload_file):
    """Tests successful loading of a valid CSV file."""
    csv_content = b"date_time,users,holiday,weather,temp,atemp,hum,windspeed\n" \
                  b"2012-09-01 00:00:00,168,0,clear,30.34,34.09,62,7.0015\n" \
                  b"2012-09-01 01:00:00,79,0,clear,29.52,34.85,74,8.9981"
    upload_file = create_mock_upload_file(csv_content)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ['users', 'holiday', 'weather', 'temp', 'atemp', 'hum', 'windspeed']
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index[0] == pd.to_datetime("2012-09-01 00:00:00")
    assert df["users"].tolist() == [168.0, 79.0]
    assert df['weather'].tolist() == ['clear', 'clear']

def test_load_data_from_csv_different_datetime_formats(create_mock_upload_file):
    """Tests loading CSV with different date/time formats."""
    csv_content = b"date_time,users\n" \
                  b"2012/09/01 00:00:00,168\n" \
                  b"09/01/2012 01:00:00,79\n" \
                  b"2012-09-01T02:00:00,69"
    upload_file = create_mock_upload_file(csv_content)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert isinstance(df.index, pd.DatetimeIndex)

def test_load_data_from_csv_invalid_datetime_format(create_mock_upload_file):
    """Tests loading CSV with invalid date/time formats."""
    csv_content = b"date_time,users\n" \
                  b"invalid-date,168\n" \
                  b"another-invalid,79"
    upload_file = create_mock_upload_file(csv_content)
    with pytest.raises(HTTPException) as excinfo:
        load_data_from_csv(upload_file)
    assert excinfo.value.status_code == 400  # Expecting 400 now
    assert "Error parsing date_time column" in excinfo.value.detail

def test_load_data_from_csv_missing_values(create_mock_upload_file):
    """Tests loading CSV with missing values."""
    csv_content = b"date_time,users,temp\n" \
                  b"2012-09-01 00:00:00,168,\n" \
                  b"2012-09-01 01:00:00,,29.52\n" \
                  b"2012-09-01 02:00:00,69,30.0"
    upload_file = create_mock_upload_file(csv_content)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    # How you assert missing values depends on how you want to handle them
    assert pd.isna(df['users'][1])
    assert pd.isna(df['temp'][0])

def test_load_data_from_csv_empty_strings(create_mock_upload_file):
    """Tests loading CSV with empty strings."""
    csv_content = b"date_time,weather\n" \
                  b"2012-09-01 00:00:00,\n" \
                  b"2012-09-01 01:00:00,clear"
    upload_file = create_mock_upload_file(csv_content)
    df = load_data_from_csv(upload_file)
    assert isinstance(df, pd.DataFrame)
    assert pd.isna(df['weather'][0])  # Check for NaN
    assert df['weather'][1] == 'clear'


if __name__ == "__main__":
    print("Testing data loader...")