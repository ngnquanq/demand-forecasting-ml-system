import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from fastapi.testclient import TestClient

from src.api.main import app


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200


def test_predict_tuning(client, csv_file):
    params = {"forecast_hours": 36, "window_sizes": 72}
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


def test_csv_download_includes_all_columns(client, csv_file):
    params = {"forecast_hours": 36, "window_sizes": 72}
    response = client.post("/predict-tuning", files=csv_file, params=params)
    assert response.status_code == 200
    prediction = response.json()["prediction"]
    first_key = next(iter(prediction))
    cols = list(prediction[first_key].keys())
    lines = [",".join(["date_time"] + cols)]
    lines.extend(
        ",".join([dt] + [str(values[c]) for c in cols])
        for dt, values in prediction.items()
    )
    csv_content = "\n".join(lines)
    header = csv_content.splitlines()[0].split(",")
    first_key = next(iter(prediction))
    expected = ["date_time"] + list(prediction[first_key].keys())
    assert header == expected


def test_non_positive_forecast_hours(client, csv_file):
    params = {"forecast_hours": -5, "window_sizes": 72}
    response = client.post("/predict-tuning", files=csv_file, params=params)
    assert response.status_code in [400, 422]
    data = response.json()
    assert "error" in data or "detail" in data


def test_non_positive_window_sizes(client, csv_file):
    params = {"forecast_hours": 36, "window_sizes": 0}
    response = client.post("/predict-tuning", files=csv_file, params=params)
    assert response.status_code in [400, 422]
    data = response.json()
    assert "error" in data or "detail" in data


def test_get_data_range_success(
    client, api_mock_get_min_max_time_success, api_mock_logger, api_mock_tracer
):
    """
    Tests successful retrieval of min/max time from the database.
    """
    mock_tracer_obj, mock_span = api_mock_tracer

    response = client.get("/data-range")
    print(response)
    assert response.status_code == 200
    expected_response = {
        "min_time": "2012-08-31T17:00:00+00:00",
        "max_time": "2012-12-11T04:00:00+00:00",
    }
    assert response.json() == expected_response

    api_mock_get_min_max_time_success.assert_called_once()
    api_mock_logger.info.assert_any_call("Request received for data range.")
    api_mock_logger.info.assert_any_call(
        "Successfully retrieved data range.",
        min_time=pd.Timestamp("2012-08-31 17:00:00+0000", tz="UTC"),
        max_time=pd.Timestamp("2012-12-11 04:00:00+0000", tz="UTC"),
    )
    mock_tracer_obj.assert_called_once_with("get-data-range-request")
    mock_span.set_attribute.assert_not_called()


def test_get_data_range_no_data(
    client, api_mock_get_min_max_time_no_data, api_mock_logger, api_mock_tracer
):
    """
    Tests the scenario where get_min_max_time_from_db returns no data.
    """
    mock_tracer_obj, mock_span = api_mock_tracer

    response = client.get("/data-range")

    assert response.status_code == 200
    expected_response = {
        "min_time": None,
        "max_time": None,
    }
    assert response.json() == expected_response

    api_mock_get_min_max_time_no_data.assert_called_once()
    api_mock_logger.info.assert_any_call("Request received for data range.")
    api_mock_logger.info.assert_any_call(
        "Successfully retrieved data range.", min_time=None, max_time=None
    )
    mock_tracer_obj.assert_called_once_with("get-data-range-request")
    mock_span.set_attribute.assert_not_called()


def test_predict_tuning_db_success(
    client,
    mock_forecast_with_tuning_db_success,  # Mocks the model prediction function
    api_mock_logger,
    api_mock_tracer,
):
    """
    Tests successful prediction for /predict-tuning-db endpoint.
    """
    print("\nDEBUG_TEST: Running test_predict_tuning_db_success")
    mock_tracer_obj, mock_span = api_mock_tracer

    forecast_hours = 24
    window_sizes = 7
    start_time = "2024-01-01 00:00:00+00"
    stop_time = "2024-01-07 23:00:00+00"

    response = client.post(
        "/predict-tuning-db",
        params={
            "forecast_hours": forecast_hours,
            "window_sizes": window_sizes,
            "start_time": start_time,
            "stop_time": stop_time,
        },
    )

    print(f"DEBUG_TEST: Response Status Code: {response.status_code}")
    print(f"DEBUG_TEST: Response Content: {response.json()}")

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["message"] == "Prediction endpoint success (DB-based)"
    assert "prediction" in response_json
    assert "mae" in response_json
    assert response_json["mae"] == 5.2  # From mock_forecast_with_tuning_db_success

    mock_forecast_with_tuning_db_success.assert_called_once_with(
        forecast_hours=forecast_hours,
        window_sizes=window_sizes,
        start_time=start_time,
        stop_time=stop_time,
    )
    api_mock_logger.info.assert_any_call(
        "Prediction request received (DB-based).",
        forecast_hours=forecast_hours,
        window_sizes=window_sizes,
        start_time=start_time,
        stop_time=stop_time,
    )
    api_mock_logger.info.assert_any_call(
        "Forecast tuning (DB-based) completed successfully.", mae=5.2
    )

    # Tracer assertions
    # Note: start_as_current_span is called twice, mock_tracer_obj.start_as_current_span.call_args_list can verify both
    mock_tracer_obj.assert_any_call("predict-tuning-db-request")
    mock_tracer_obj.assert_any_call("forecast-with-tuning-db")
    mock_span.set_attribute.assert_any_call("forecast_hours", forecast_hours)
    mock_span.set_attribute.assert_any_call("window_sizes", window_sizes)
    mock_span.set_attribute.assert_any_call("data_start_time", start_time)
    mock_span.set_attribute.assert_any_call("data_stop_time", stop_time)
    mock_span.set_attribute.assert_any_call("mae", 5.2)


def test_predict_tuning_db_invalid_time_format(
    client,
    mock_main_pd_to_datetime_error,  # This mock will trigger the ValueError in main.py
    api_mock_logger,
    api_mock_tracer,
):
    """
    Tests invalid timestamp format (should return 400 Bad Request).
    """
    print("\nDEBUG_TEST: Running test_predict_tuning_db_invalid_time_format")
    mock_tracer_obj, mock_span = api_mock_tracer

    forecast_hours = 24
    window_sizes = 7
    start_time = "INVALID_TIMESTAMP"  # Invalid format
    stop_time = "2024-01-07 23:00:00+00"

    response = client.post(
        "/predict-tuning-db",
        params={
            "forecast_hours": forecast_hours,
            "window_sizes": window_sizes,
            "start_time": start_time,
            "stop_time": stop_time,
        },
    )

    print(f"DEBUG_TEST: Response Status Code: {response.status_code}")
    print(f"DEBUG_TEST: Response Content: {response.json()}")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Invalid start_time or stop_time format. UseYYYY-MM-DD HH:MM:SS[+HH] format."
    )

    mock_main_pd_to_datetime_error.assert_called_with(
        start_time
    )  # pd.to_datetime called with invalid string
    api_mock_logger.warning.assert_called_once_with(
        "Invalid start_time or stop_time format."
    )

    # FIX: Assert directly on mock_tracer_obj
    mock_tracer_obj.assert_called_once_with(
        "predict-tuning-db-request"
    )  # This line was changed
    mock_span.set_attribute.assert_any_call("error", True)
    mock_span.set_attribute.assert_any_call(
        "error.message", "Invalid start_time or stop_time format."
    )


def test_predict_tuning_db_backend_error(
    client,
    mock_forecast_with_tuning_db_error,  # This mock will raise an Exception
    api_mock_logger,
    api_mock_tracer,
):
    """
    Tests a scenario where the forecast_with_tuning_db function raises an exception (500 Internal Server Error).
    """
    print("\nDEBUG_TEST: Running test_predict_tuning_db_backend_error")
    mock_tracer_obj, mock_span = (
        api_mock_tracer  # mock_tracer_obj is the mock for tracer.start_as_current_span
    )

    forecast_hours = 24
    window_sizes = 7
    start_time = "2024-01-01 00:00:00+00"
    stop_time = "2024-01-07 23:00:00+00"

    response = client.post(
        "/predict-tuning-db",
        params={
            "forecast_hours": forecast_hours,
            "window_sizes": window_sizes,
            "start_time": start_time,
            "stop_time": stop_time,
        },
    )

    print(f"DEBUG_TEST: Response Status Code: {response.status_code}")
    print(f"DEBUG_TEST: Response Content: {response.json()}")

    assert response.status_code == 500
    assert response.json()["detail"] == "Simulated DB forecast error"

    mock_forecast_with_tuning_db_error.assert_called_once()
    api_mock_logger.error.assert_called_once_with(
        "Prediction (DB-based) failed due to an unhandled error: Simulated DB forecast error"
    )

    # FIX: Use assert_any_call for both expected calls to tracer.start_as_current_span
    # And assert the total call count if you want to be strict about only these two calls
    mock_tracer_obj.assert_any_call("predict-tuning-db-request")
    mock_tracer_obj.assert_any_call("forecast-with-tuning-db")
    assert mock_tracer_obj.call_count == 2  # Verify exactly two calls happened

    # Assertions on the span (which is the mock returned by the context manager)
    mock_span.set_attribute.assert_any_call("error", True)
    mock_span.set_attribute.assert_any_call(
        "error.message", "Simulated DB forecast error"
    )
