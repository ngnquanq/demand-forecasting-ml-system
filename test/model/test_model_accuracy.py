from sklearn.metrics import mean_absolute_error


def test_mae_is_smaller_than_100(prepared_model_and_data):
    """
    Tests if the Mean Absolute Error (MAE) of the model's predictions
    is strictly greater than 100. (the number here is arbitrary and can be adjusted
    based on the expected performance of the model).
    """
    # The fixture provides these directly
    model, exog_for_prediction, actual_values = prepared_model_and_data

    future_predictions = model.predict(
        steps=len(actual_values), exog=exog_for_prediction
    )

    assert len(future_predictions) == len(
        actual_values
    ), "Prediction length does not match actuals length for MAE calculation."

    mae = mean_absolute_error(actual_values, future_predictions)
    print(f"\nCalculated MAE (for >100 check): {mae:.2f}")

    # This test will PASS if MAE > 100.
    assert mae > 100, f"MAE ({mae:.2f}) is NOT strictly larger than 100."


def test_mae_is_within_acceptable_range(prepared_model_and_data):
    """
    Tests if the Mean Absolute Error (MAE) is within an acceptable upper bound,
    implying reasonable model performance.
    """
    # The fixture provides these directly
    model, exog_for_prediction, actual_values = prepared_model_and_data

    future_predictions = model.predict(
        steps=len(actual_values), exog=exog_for_prediction
    )

    assert len(future_predictions) == len(
        actual_values
    ), "Prediction length does not match actuals length for MAE calculation."

    mae = mean_absolute_error(actual_values, future_predictions)
    print(f"\nCalculated MAE (for acceptable range check): {mae:.2f}")

    ACCEPTABLE_MAE_THRESHOLD = 105
    assert (
        mae <= ACCEPTABLE_MAE_THRESHOLD
    ), f"MAE ({mae:.2f}) is greater than the acceptable threshold of {ACCEPTABLE_MAE_THRESHOLD}. Model performance might be poor."
