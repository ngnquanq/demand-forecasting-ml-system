import os
import sys
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from fastapi import UploadFile
from lightgbm import LGBMRegressor
from opentelemetry import trace
from optuna.trial import Trial
from skforecast.model_selection import (
    TimeSeriesFold,
    bayesian_search_forecaster,
)
from skforecast.preprocessing import RollingFeatures
from skforecast.recursive import ForecasterRecursive

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_loader import *
from src.model.forecast_model import *

tracer = trace.get_tracer(__name__)


def run_bayesian_hyperparameter_search_and_fit(
    data: pd.DataFrame,
    end_validation: Union[str, pd.Timestamp],
    exog_features: List[str],
    window_features: RollingFeatures = None,
    transformer_exog: Optional[Any] = None,
    n_trials: int = 20,
    random_state: int = 15926,
    steps: Optional[int] = None,
    initial_train_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Perform a Bayesian hyperparameter (including lag) search and return:
      - best_params: dictionary of optimal LightGBM hyperparameters + random_state & verbose flags
      - best_lags: integer or list of integers indicating the chosen lag configuration
      - model: a ForecasterRecursive instance fitted on all data up to end_validation

    Parameters
    ----------
    data : pd.DataFrame
        Must have a DatetimeIndex (with frequency) and a 'users' column for the target. :contentReference[oaicite:3]{index=3}
    end_validation : str or pd.Timestamp
        Timestamp (inclusive) that designates the end of the training+validation period. :contentReference[oaicite:4]{index=4}
    exog_features : list of str
        Column names (besides 'users') to use as exogenous regressors. :contentReference[oaicite:5]{index=5}
    window_features : dict (optional)
        Maps feature names to callables (e.g., rolling functions) to generate window features. Requires Skforecast v0.14.0+. :contentReference[oaicite:6]{index=6}
    transformer_exog : TransformerMixin (optional)
        scikit-learn–compatible transformer to apply to exogenous features. :contentReference[oaicite:7]{index=7}
    n_trials : int, default 20
        Number of Optuna trials in the Bayesian search. More trials => finer hyperparameter exploration. :contentReference[oaicite:8]{index=8}
    random_state : int, default 15926
        Seed for both LightGBM regressor and Optuna sampler to ensure reproducible results. :contentReference[oaicite:9]{index=9}
    steps : int or None
        Number of folds ahead for TimeSeriesFold. If None, a single-fold backtest is used to avoid shape mismatches. :contentReference[oaicite:10]{index=10}
    initial_train_size : int or None
        If specified along with steps, sets the initial number of observations for the first fold. Must satisfy:
        `initial_train_size ≥ max(lags) + (number_of_training_rows_after_dropping_lags)`. :contentReference[oaicite:11]{index=11}

    Returns
    -------
    dict
        {
            "best_params": {
                "n_estimators": int,
                "max_depth": int,
                "min_child_samples": int,
                "learning_rate": float,
                "feature_fraction": float,
                "num_leaves": int,
                "reg_alpha": float,
                "reg_lambda": float,
                "max_bin": int,
                "lags": int or list of int,
                "random_state": int,
                "verbose": int
            },
            "best_lags": int or list of int,
            "model": ForecasterRecursive  # already fitted on data up to end_validation
        }
    """
    # 1. Validate and set index frequency :contentReference[oaicite:12]{index=12}
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("`data` must have a DatetimeIndex before tuning.")
    if data.index.freq is None:
        data.index.freq = "h"  # or another appropriate frequency string

    # 2. Define the Optuna search space, including lags as a categorical parameter :contentReference[oaicite:13]{index=13}
    lags_grid = [48, 72, [1, 2, 3, 23, 24, 25, 167, 168, 169]]

    def search_space(trial: Trial) -> Dict[str, Any]:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 300, 1000, step=100),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_samples": trial.suggest_int("min_child_samples", 25, 500),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.5),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
            "num_leaves": trial.suggest_int("num_leaves", 20, 150),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 1.0),
            "max_bin": trial.suggest_int("max_bin", 50, 250),
            "lags": trial.suggest_categorical("lags", lags_grid),
        }

    # 3. Instantiate a placeholder ForecasterRecursive (lags will be overridden by search) :contentReference[oaicite:14]{index=14}
    forecaster = ForecasterRecursive(
        regressor=LGBMRegressor(random_state=random_state, verbose=-1),
        lags=72,
        window_features=window_features,
        transformer_exog=transformer_exog,
        fit_kwargs={"categorical_feature": "auto"},
    )

    # 4. Configure TimeSeriesFold for backtesting :contentReference[oaicite:15]{index=15}
    if steps is None and initial_train_size is None:
        cv_search = TimeSeriesFold(steps=None, initial_train_size=None)
    else:
        cv_search = TimeSeriesFold(steps=steps, initial_train_size=initial_train_size)

    # 5. Run the Bayesian search over the training+validation period :contentReference[oaicite:16]{index=16}
    results_search, frozen_trial = bayesian_search_forecaster(
        forecaster=forecaster,
        y=data.loc[:end_validation, "users"],
        exog=data.loc[:end_validation, exog_features],
        cv=cv_search,
        search_space=search_space,
        metric="mean_absolute_error",
        n_trials=n_trials,
        random_state=random_state,
        return_best=True,
        verbose=False,
        show_progress=True,
    )
    print(type(results_search))
    print(results_search)
    # 6. Extract the best parameters and lags from the results DataFrame :contentReference[oaicite:17]{index=17}
    best_params = results_search["params"].iloc[0].values()
    best_params = dict(results_search["params"].iloc[0])
    best_params["random_state"] = random_state
    best_params["verbose"] = -1
    best_lags = results_search["lags"].iloc[0]

    return {
        "best_params": best_params,
        "best_lags": best_lags,
    }


def train_forecaster_with_best_params(
    data: pd.DataFrame,
    end_validation: Union[str, pd.Timestamp],
    exog_features: List[str],
    window_features: Optional[List[Any]] = None,
    transformer_exog: Optional[Any] = None,
    best_params: Dict[str, Any] = None,
    best_lags: Union[int, List[int]] = None,
) -> ForecasterRecursive:
    """
    1. Given best_params and best_lags (from hyperparameter search),
       create a new ForecasterRecursive with those settings.
    2. Fit it on the combined data up through end_validation.

    Returns
    -------
    ForecasterRecursive: Fitted model ready for prediction.
    """
    if best_params is None or best_lags is None:
        raise ValueError("`best_params` and `best_lags` must be provided.")

    # 1. Create a fresh LightGBM regressor with best_params (except 'lags')
    lgbm_kwargs = {
        k: v for k, v in best_params.items() if k not in ["random_state", "verbose"]
    }
    regressor = LGBMRegressor(**lgbm_kwargs)  # :contentReference[oaicite:38]{index=38}

    # 2. Instantiate ForecasterRecursive with best_lags
    final_forecaster = ForecasterRecursive(
        regressor=regressor,
        lags=best_lags,
        window_features=window_features,
        transformer_exog=transformer_exog,
        fit_kwargs={"categorical_feature": "auto"},
    )

    # 3. Fit on all data ≤ end_validation
    final_forecaster.fit(
        y=data.loc[:end_validation, "users"],
        exog=data.loc[:end_validation, exog_features],
    )

    return final_forecaster


def forecast_with_tuning(file: UploadFile, forecast_hours: int, window_sizes: int):
    with tracer.start_as_current_span("forecast_with_tuning") as root_span:
        # Step 1: Load data
        with tracer.start_as_current_span("load-data"):
            data = load_data_from_csv(file)

        # Step 2: Feature extraction
        with tracer.start_as_current_span("extract-features") as span:
            y = data["users"].copy()
            exog = data.drop(columns=["users"]).copy()
            exog_features = exog.columns.to_list()
            span.set_attribute("num_features", len(exog_features))

        # Step 3: Validation slicing
        with tracer.start_as_current_span("prepare-validation-window"):
            end_validation = data.index[-forecast_hours - 1].strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            end_validation_dt = pd.to_datetime(end_validation) + pd.Timedelta(hours=1)

        # Step 4: Create transformers
        with tracer.start_as_current_span("init-transformers"):
            window_features = RollingFeatures(stats=["mean"], window_sizes=window_sizes)
            encoder = create_encoder()

        # Step 5: Hyperparameter tuning
        with tracer.start_as_current_span("tune-model") as tuning_span:
            result = run_bayesian_hyperparameter_search_and_fit(
                data=data,
                end_validation=end_validation,
                exog_features=exog_features,
                window_features=window_features,
                transformer_exog=encoder,
                n_trials=10,
                steps=forecast_hours,
                initial_train_size=round(len(y) * 0.9),
                random_state=2025,
            )
            tuning_span.set_attribute("best_score", result.get("best_score", "n/a"))

        # Step 6: Train final model
        with tracer.start_as_current_span("train-best-model"):
            model = train_forecaster_with_best_params(
                data=data,
                end_validation=end_validation,
                exog_features=exog_features,
                window_features=window_features,
                transformer_exog=encoder,
                best_params=result["best_params"],
                best_lags=result["best_lags"],
            )

        # Step 7: Make prediction
        with tracer.start_as_current_span("make-predictions"):
            exog_pred = data.loc[end_validation_dt:, exog_features].head(forecast_hours)
            predictions = model.predict(steps=forecast_hours, exog=exog_pred)

        # Step 8: Post-process forecast
        with tracer.start_as_current_span("combine-results") as combine_span:
            future_index = exog_pred.index
            forecast_df = pd.DataFrame(
                {
                    "date_time": future_index,
                    "predicted_users": np.ceil(predictions).astype(int),
                    "real_users": data.loc[future_index, "users"].values,
                }
            )
            forecast_df.set_index("date_time", inplace=True)
            forecast_df = pd.concat([forecast_df, exog_pred], axis=1)

        # Step 9: Evaluate
        with tracer.start_as_current_span("evaluate") as eval_span:
            mae = mean_absolute_error(
                forecast_df["real_users"], forecast_df["predicted_users"]
            )
            forecast_df.index = forecast_df.index.strftime("%Y-%m-%d %H:%M:%S")
            eval_span.set_attribute("mae", mae)

        return forecast_df, mae
