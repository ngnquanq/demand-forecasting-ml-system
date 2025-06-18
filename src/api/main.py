import logging
import os
import sys
import time

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_loader import *
from src.model.forecast_model import *

# Define constants
EXTERNAL_API = "http://localhost:8081/external-api"

# Configure logger
logger = logging.getLogger("app")

app = FastAPI()
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# acquire tracer
tracer = trace.get_tracer("application.tracer")


# Add middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Log the incoming request
    logger.info(f"Request started: {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}s"
        )
        return response
    except Exception as e:
        logger.error(
            f"Request failed: {request.method} {request.url.path} - Error: {str(e)}"
        )
        raise


@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Hello World"}


@app.post("/predict-tuning")
async def predict_tuning(
    file: UploadFile = File(...), forecast_hours: int = 36, window_sizes: int = 72
):
    if int(forecast_hours) <= 0 or int(window_sizes) <= 0:
        raise HTTPException(
            status_code=400, detail="forecast_hours and window_sizes must be > 0"
        )
    try:
        forecast_df, mae = forecast_with_tuning(file, forecast_hours, window_sizes)
        return {
            "message": "Prediction endpoint success",
            "prediction": forecast_df.to_dict(orient="index"),
            "mae": mae,
        }
    except Exception as e:
        logger.exception("Prediction failed.")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("Application started")
