import sys 
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from src.api.main import app
import pandas as pd

def test_read_root(client):
    response = client.get("/")
    assert response.status_code==200
def test_predict_tuning(client, csv_file):
    params = {
        'forecast_hours': 36,
        'window_sizes': 72
    }
    response = client.post("/predict-tuning", files=csv_file, params=params)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Prediction endpoint success"
    assert "prediction" in data
    assert "mae" in data

def test_static_index(client):
    response = client.get("/static/index.html")
    assert response.status_code == 200

def _convert_to_csv(prediction: dict) -> str:
    first_key = next(iter(prediction))
    cols = list(prediction[first_key].keys())
    lines = [','.join(['date_time'] + cols)]
    lines.extend(
        ','.join([dt] + [str(values[c]) for c in cols])
        for dt, values in prediction.items()
    )
    return '\n'.join(lines)

def test_csv_download_includes_all_columns(client, csv_file):
    params = {
        'forecast_hours': 36,
        'window_sizes': 72
    }
    response = client.post("/predict-tuning", files=csv_file, params=params)
    assert response.status_code == 200
    prediction = response.json()["prediction"]
    csv_content = _convert_to_csv(prediction)
    header = csv_content.splitlines()[0].split(',')
    first_key = next(iter(prediction))
    expected = ['date_time'] + list(prediction[first_key].keys())
    assert header == expected

def test_non_positive_forecast_hours(client, csv_file):
    params = {
        'forecast_hours': -5,
        'window_sizes': 72
    }
    response = client.post("/predict-tuning", files=csv_file, params=params)
    assert response.status_code in [400, 422]
    data = response.json()
    assert "error" in data or "detail" in data

def test_non_positive_window_sizes(client, csv_file):
    params = {
        'forecast_hours': 36,
        'window_sizes': 0
    }
    response = client.post("/predict-tuning", files=csv_file, params=params)
    assert response.status_code in [400, 422]
    data = response.json()
    assert "error" in data or "detail" in data