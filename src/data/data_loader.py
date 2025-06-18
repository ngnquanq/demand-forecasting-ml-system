from io import StringIO

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sklearn.compose import make_column_selector, make_column_transformer
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import FunctionTransformer, OrdinalEncoder, TargetEncoder


def load_data_from_csv(file: UploadFile = File(...)) -> pd.DataFrame:
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        MAX_FILE_SIZE = 100 * 1024 * 1024
        content = file.file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, detail="File too large. Maximum size is 100MB"
            )

        encodings = ["utf-8", "latin-1", "cp1252"]
        for encoding in encodings:
            try:
                content_str = content.decode(encoding)
                break
            except UnicodeDecodeError:
                if encoding == encodings[-1]:
                    raise HTTPException(
                        status_code=400,
                        detail="Unable to decode file. Please ensure it's a valid CSV file",
                    )
                continue

        text_io = StringIO(content_str)
        data = pd.read_csv(text_io)
        if "date_time" not in data.columns:
            raise HTTPException(
                status_code=400, detail="CSV must contain a 'date_time' column"
            )

        try:
            # Use format='mixed' for flexible date parsing
            data["date_time"] = pd.to_datetime(
                data["date_time"], format="mixed", errors="raise"
            )  # Explicit errors='raise'
            data.set_index("date_time", inplace=True)
        except ValueError as e:  # Catch ValueError specifically
            raise HTTPException(
                status_code=400, detail=f"Error parsing date_time column: {str(e)}"
            )
        except (
            Exception
        ) as e:  # Catch other exceptions (less specific, but a safety net)
            raise HTTPException(
                status_code=400, detail=f"Unexpected error parsing date_time: {str(e)}"
            )

        return data
    except HTTPException as hte:  # Catch HTTPExceptions directly
        raise hte
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve data: {str(e)}"
        )


def create_encoder():
    ordinal_encoder = make_column_transformer(
        (
            OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1,
                encoded_missing_value=-1,
            ),
            make_column_selector(dtype_exclude=np.number),
        ),
        remainder="passthrough",
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")
    return ordinal_encoder
