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
async def predict_tuning(file: UploadFile = File(...), forecast_hours: int = 36, window_sizes: int = 72):
    if int(forecast_hours) <= 0 or int(window_sizes) <= 0:
        raise HTTPException(status_code=400, detail="forecast_hours and window_sizes must be > 0")
    try:
        forecast_df, mae = forecast_with_tuning(file, forecast_hours, window_sizes)
        return {
            "message": "Prediction endpoint success",
            "prediction": forecast_df.to_dict(orient="index"),
            "mae": mae
        }
    except Exception as e:
        logger.exception("Prediction failed.")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Application started")
    