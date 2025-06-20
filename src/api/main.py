import os
import sys
import time
import json # Still useful if you manually construct JSON messages for some reason, but less critical for output
from functools import wraps

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from loguru import logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_loader import *
from src.model.forecast_model import *

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENABLE_DIAGNOSE = os.getenv("ENABLE_DIAGNOSE", "False").lower() == "true" # avoid exploding logs size

# 1. Remove all default handlers to have full control
logger.remove()

# 2. Add a single sink: sys.stderr (or sys.stdout, usually stderr for errors/warnings)
logger.add(
    sys.stderr, # Use stderr for error/warning logs
    level=LOG_LEVEL,
    serialize=True, 
    enqueue=True, 
    backtrace=True,
    diagnose=ENABLE_DIAGNOSE,  
)


logger.configure(
    extra={"app_name": "ForecastApp", "environment": os.getenv("APP_ENV", "development")}
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# acquire tracer
tracer = trace.get_tracer("application.tracer")

def log_request_middleware(func):
    @wraps(func)
    async def wrapper(request: Request, call_next):
        start_time = time.time()
        with logger.contextualize(
            method=request.method,
            path=request.url.path,
            client_host=request.client.host,
            client_port=request.client.port
        ):
            logger.info("Request started.")
            try:
                response = await call_next(request)
                process_time = time.time() - start_time
                logger.info("Request completed.", status_code=response.status_code, process_time_s=f"{process_time:.2f}")
                return response
            except Exception as e:
                logger.exception("Request failed.")
                raise
    return wrapper

@app.middleware("http")
@log_request_middleware
async def dispatch_middleware(request: Request, call_next):
    return await call_next(request)

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Hello World"}


@app.post("/predict-tuning")
@logger.catch # Use loguru's decorator for automatic exception catching and detailed logging
async def predict_tuning(
    file: UploadFile = File(...), forecast_hours: int = 36, window_sizes: int = 72
):
    logger.info("Prediction request received.",
                filename=file.filename,
                forecast_hours=forecast_hours,
                window_sizes=window_sizes)

    if int(forecast_hours) <= 0 or int(window_sizes) <= 0:
        # Use warning or error for invalid input, and include relevant data
        logger.warning(
            "Invalid input for forecast_hours or window_sizes.",
            forecast_hours=forecast_hours,
            window_sizes=window_sizes
        )
        raise HTTPException(
            status_code=400, detail="forecast_hours and window_sizes must be > 0"
        )
    try:
        with logger.contextualize(model_operation="forecast_tuning"):
            forecast_df, mae = forecast_with_tuning(file, forecast_hours, window_sizes)
            logger.info("Forecast tuning completed successfully.", mae=mae)
            return {
                "message": "Prediction endpoint success",
                "prediction": forecast_df.to_dict(orient="index"),
                "mae": mae,
            }
    except Exception as e:
        logger.error(f"Prediction failed due to an unhandled error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("Application starting up...")
