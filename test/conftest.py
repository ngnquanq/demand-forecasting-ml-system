# test/conftest.py

import pytest
from pathlib import Path
from fastapi import UploadFile
from io import BytesIO
from fixtures.model_setup import prepare_model_and_data
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.api.main import app
from fastapi.testclient import TestClient

@pytest.fixture
def csv_file_path() -> Path:
    return Path(__file__).parent / "test_data.csv"

@pytest.fixture
def csv_file(csv_file_path):
    with csv_file_path.open("rb") as f:
        yield {
            "file": ("test_data.csv", f, "text/csv")
        }

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
