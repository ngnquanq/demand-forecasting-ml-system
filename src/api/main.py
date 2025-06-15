'''
Things to improve:
1. Create a dashboard to visualize the results of the forecast (using gradio)
'''
import pandas as pd 
import numpy as np 
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
import math
import os 
import time
from sklearn.metrics import mean_absolute_error

# Modelling and Forecasting
# ==============================================================================

import skforecast
from skforecast.recursive import ForecasterEquivalentDate, ForecasterRecursive
from skforecast.model_selection import (
    TimeSeriesFold,
    OneStepAheadFold,
    bayesian_search_forecaster,
    backtesting_forecaster,
)
from skforecast.preprocessing import RollingFeatures
from skforecast.feature_selection import select_features
from skforecast.metrics import calculate_coverage
from fastapi.staticfiles import StaticFiles

import sys
# ==============================================================================
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model.forecast_model import *
from src.data.data_loader import * 

# Define constants 
EXTERNAL_API = "http://localhost:8081/external-api"  

# Configure logger
logger = logging.getLogger('app')

app = FastAPI()
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Add middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log the incoming request
    logger.info(f"Request started: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}s")
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)}")
        raise

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Hello World"}

@app.post("/predict-tuning")
async def predict_tuning(file: UploadFile = File(...), forecast_hours: int=36,
                         window_sizes=72):
    # validate input
    if int(forecast_hours) <= 0:
        logger.error(f"Invalid forecast_hours({forecast_hours}): must be greater than 0")
        raise HTTPException(status_code=400, detail="forecast_hours must be greater than 0")
    if int(window_sizes) <= 0:
        logger.error(f"Invalid window_sizes({window_sizes}): must be greater than 0")
        raise HTTPException(status_code=400, detail="window_sizes must be greater than 0")
    # Load the data 
    data = load_data_from_csv(file)
    y = data["users"].copy()
    exog = data.drop(columns=["users"]).copy()
    exog_features = exog.columns.to_list()
    # Create some parameter
    end_validation = data.index[-forecast_hours-1].strftime('%Y-%m-%d %H:%M:%S')
    window_features = RollingFeatures(stats=['mean'], window_sizes=72)
    encoder = create_encoder()
    # Run the bayesian serach
    result = run_bayesian_hyperparameter_search_and_fit(
                data = data, 
                end_validation=end_validation,
                exog_features=exog_features,
                window_features=window_features, 
                transformer_exog=encoder,
                n_trials=10,
                steps=36,
                initial_train_size=round(len(y)*0.9),
                random_state=2025
            )
    model = train_forecaster_with_best_params(
            data=data,
            end_validation=end_validation,
            exog_features=exog_features,
            window_features=window_features,
            transformer_exog=encoder,
            best_params=result["best_params"],
            best_lags=result["best_lags"]
            ) 
    end_validation_dt = pd.to_datetime(end_validation) + pd.Timedelta(hours=1)

    exog_for_prediction = data.loc[end_validation_dt:, exog_features]

    future_predictions = model.predict(
        steps=forecast_hours,
        exog=exog_for_prediction
    )

    future_index = data.loc[end_validation_dt:].index
    forecast_df = pd.DataFrame({
        "date_time": future_index,
        "predicted_users": np.ceil(future_predictions).astype(int),
        "real_users": data.loc[future_index, 'users'].values
    })
    forecast_df.set_index("date_time", inplace=True)
    forecast_df = pd.concat([forecast_df,exog_for_prediction], axis=1)
    actual_y = forecast_df["real_users"]
    pred_y = forecast_df["predicted_users"]
    mae = mean_absolute_error(actual_y, pred_y)
    forecast_df.index = forecast_df.index.strftime("%Y-%m-%d %H:%M:%S")

    logger.info("Prediction completed successfully")
    return {"message": "Prediction endpoint success", 
            "prediction": forecast_df.to_dict(orient="index"),
            "mae": mae}
    

if __name__ == "__main__":
    logger.info("Application started")
    