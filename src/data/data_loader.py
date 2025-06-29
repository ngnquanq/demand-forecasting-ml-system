import os
from io import StringIO

import numpy as np
import pandas as pd
import psycopg2
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger
from psycopg2 import Error
from sklearn.compose import make_column_selector, make_column_transformer
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import FunctionTransformer, OrdinalEncoder, TargetEncoder

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_NAME = "postgres"
DEFAULT_DB_USER = "postgres"
DEFAULT_DB_PASSWORD = "password"
DEFAULT_SCHEMA_NAME = "application"
DEFAULT_TABLE_NAME = "feature"
DEFAULT_TIME_COLUMN = "date_time"


def get_db_connection_params():
    """
    Retrieves database connection parameters, prioritizing environment variables
    and falling back to default hardcoded values.
    """
    host = os.getenv("DB_HOST", DEFAULT_DB_HOST)
    database = os.getenv("DB_NAME", DEFAULT_DB_NAME)
    user = os.getenv("DB_USER", DEFAULT_DB_USER)
    password = os.getenv("DB_PASSWORD", DEFAULT_DB_PASSWORD)
    schema_name = os.getenv("DB_SCHEMA", DEFAULT_SCHEMA_NAME)
    table_name = os.getenv("DB_TABLE", DEFAULT_TABLE_NAME)
    time_column = os.getenv("TIME_COLUMN", DEFAULT_TIME_COLUMN)

    return host, database, user, password, schema_name, table_name, time_column


def get_min_max_time_from_db():
    # Retrieve parameters using the new helper function
    host, database, user, password, schema_name, table_name, time_column = (
        get_db_connection_params()
    )

    connection = None
    min_time = None
    max_time = None

    logger.info(
        f"Attempting to connect to DB for min/max time from {schema_name}.{table_name}..."
    )

    try:
        connection = psycopg2.connect(
            user=user, password=password, host=host, port="5432", database=database
        )
        logger.info("Successfully connected to PostgreSQL for min/max time retrieval.")

        cursor = connection.cursor()

        sql_query = f'SELECT MIN("{time_column}"), MAX("{time_column}") FROM "{schema_name}"."{table_name}";'

        logger.debug(f"Executing min/max query: {sql_query}")

        cursor.execute(sql_query)
        result = cursor.fetchone()

        if result:
            min_time_raw, max_time_raw = result
            if min_time_raw and max_time_raw:
                min_time = pd.to_datetime(min_time_raw, utc=True)
                max_time = pd.to_datetime(max_time_raw, utc=True)
                logger.info(f"Retrieved min_time: {min_time}, max_time: {max_time}")
            else:
                logger.warning(
                    f"No min/max time values found in {schema_name}.{table_name}."
                )
        else:
            logger.warning(
                f"No results returned for min/max query on {schema_name}.{table_name}."
            )

        return min_time, max_time

    except (Exception, Error) as error:
        logger.error(f"Error during min/max time retrieval from PostgreSQL: {error}")
        raise error

    finally:
        if connection:
            connection.close()
            logger.info("PostgreSQL connection for min/max time closed.")


def get_data_as_dataframe_filtered(
    host,
    database,
    user,
    password,
    schema_name,
    table_name,
    time_column="date_time",
    columns_to_select="*",
    start_time=None,
    stop_time=None,
):
    connection = None
    df = None

    logger.info(
        f"Attempting to connect to DB for data loading from {schema_name}.{table_name}..."
    )

    try:
        connection = psycopg2.connect(
            user=user, password=password, host=host, port="5432", database=database
        )
        logger.info("Successfully connected to PostgreSQL.")

        sql_query = f'SELECT {columns_to_select} FROM "{schema_name}"."{table_name}"'

        where_clauses = []
        if start_time:
            where_clauses.append(f'"{time_column}" >= %s')
        if stop_time:
            where_clauses.append(f'"{time_column}" <= %s')

        query_params = []
        if start_time:
            query_params.append(start_time)
        if stop_time:
            query_params.append(stop_time)

        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
        sql_query += ";"

        logger.debug(f"Executing query: {sql_query} with params: {query_params}")

        cursor = connection.cursor()
        cursor.execute(sql_query, tuple(query_params))
        data = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        df = pd.DataFrame(data, columns=column_names)

        if not df.empty:
            df = df.set_index(time_column)
            df.index = pd.to_datetime(df.index, utc=True)
            logger.info(
                f"Successfully retrieved {len(df)} rows and converted to DataFrame."
            )
        else:
            logger.warning(
                f"No data retrieved from {schema_name}.{table_name} for the specified time range."
            )

        return df

    except (Exception, Error) as error:
        logger.error(f"Error during data retrieval from PostgreSQL: {error}")
        return None

    finally:
        if connection:
            connection.close()
            logger.info("PostgreSQL connection closed.")


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


if __name__ == "__main__":
    pass
