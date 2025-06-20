# test/conftest.py

import os
import sys
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from fixtures.model_setup import prepare_model_and_data

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient

from src.api.main import app


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
def client():
    return TestClient(app)


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
