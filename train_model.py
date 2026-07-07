#!/usr/bin/env python3
"""
Phase 2 - Model Training
Loads merged_features.csv, engineers features, trains XGBoost with
TimeSeriesSplit cross-validation, and exports model/model.pkl.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor

DATA_PATH = "data/raw/merged_features.csv"
MODEL_DIR = "model"
TARGET    = "ubs_sell_idr"

os.makedirs(MODEL_DIR, exist_ok=True)

EXCLUDE_COLS = {"ubs_sell_idr", "ubs_buyback_idr", "implied_idr_per_gram", "ubs_premium_pct"}


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col="date", parse_dates=True)
    df.sort_index(inplace=True)
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for lag in [1, 2, 3, 5, 7]:
        df[f"xauusd_lag{lag}"]   = df["xauusd"].shift(lag)
        df[f"usdidr_lag{lag}"]   = df["usdidr"].shift(lag)
        df[f"ubs_sell_lag{lag}"] = df[TARGET].shift(lag)

    for window in [5, 10, 20]:
        df[f"xauusd_ma{window}"]   = df["xauusd"].rolling(window).mean()
        df[f"usdidr_ma{window}"]   = df["usdidr"].rolling(window).mean()
        df[f"ubs_sell_ma{window}"] = df[TARGET].rolling(window).mean()

    df["xauusd_pct_change"] = df["xauusd"].pct_change()
    df["usdidr_pct_change"] = df["usdidr"].pct_change()
    df["implied_x_1g"]      = (df["xauusd"] / 31.1035) * df["usdidr"]
    df["day_of_week"]       = df.index.dayofweek
    df["month"]             = df.index.month

    df.dropna(inplace=True)
    return df


def get_features(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in EXCLUDE_COLS]


def regression_metrics(y_true, y_pred) -> dict:
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5
    mape = (abs((y_true - y_pred) / y_true) * 100).mean()
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "mape": round(mape, 4)}


def to_log(y):
    return np.log1p(y)


def from_log(y):
    return np.expm1(y)


def build_model() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        random_state=42,
        verbosity=0,
    )


def cross_validate(df: pd.DataFrame, features: list[str]) -> list[dict]:
    X  = df[features].values
    y  = df[TARGET].values
    y_log = to_log(y)

    tscv    = TimeSeriesSplit(n_splits=5)
    results = []

    print("TimeSeriesSplit cross-validation (5 folds):")
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
        model = build_model()
        model.fit(
            X[train_idx], y_log[train_idx],
            eval_set=[(X[val_idx], y_log[val_idx])],
            verbose=False,
        )
        preds = from_log(model.predict(X[val_idx]))
        m = regression_metrics(y[val_idx], preds)
        results.append(m)
        print(
            f"  Fold {fold}  |  train={len(train_idx)}  val={len(val_idx)}"
            f"  |  MAE=Rp{m['mae']:>10,.0f}  RMSE=Rp{m['rmse']:>10,.0f}  MAPE={m['mape']:.2f}%"
        )

    mean_mae  = sum(r["mae"]  for r in results) / len(results)
    mean_rmse = sum(r["rmse"] for r in results) / len(results)
    mean_mape = sum(r["mape"] for r in results) / len(results)
    print(f"\n  Mean  |                             "
          f"  MAE=Rp{mean_mae:>10,.0f}  RMSE=Rp{mean_rmse:>10,.0f}  MAPE={mean_mape:.2f}%")

    return results


def train_final(df: pd.DataFrame, features: list[str]) -> XGBRegressor:
    X     = df[features].values
    y_log = to_log(df[TARGET].values)

    model = build_model()
    model.fit(X, y_log, verbose=False)
    return model


if __name__ == "__main__":
    print(f"Loading {DATA_PATH} ...")
    raw = load_data(DATA_PATH)
    print(f"  {len(raw)} rows\n")

    print("Engineering features...")
    df = engineer_features(raw)
    features = get_features(df)
    print(f"  {len(df)} rows after dropping NaN from lags")
    print(f"  {len(features)} features\n")

    cv_results = cross_validate(df, features)

    print("\nTraining final model on full dataset...")
    model = train_final(df, features)

    final_preds   = from_log(model.predict(df[features].values))
    final_metrics = regression_metrics(df[TARGET].values, final_preds)
    print(f"  Train MAE : Rp{final_metrics['mae']:,.0f}")
    print(f"  Train MAPE: {final_metrics['mape']:.2f}%")

    print("\nTop 10 feature importances:")
    importances = (
        pd.Series(model.feature_importances_, index=features)
        .sort_values(ascending=False)
    )
    for feat, imp in importances.head(10).items():
        print(f"  {feat:<30}  {imp:.4f}")

    model_path    = os.path.join(MODEL_DIR, "model.pkl")
    features_path = os.path.join(MODEL_DIR, "feature_names.json")
    metrics_path  = os.path.join(MODEL_DIR, "metrics.json")

    joblib.dump(model, model_path)

    with open(features_path, "w") as f:
        json.dump(features, f, indent=2)

    with open(metrics_path, "w") as f:
        json.dump({
            "cv_folds":       cv_results,
            "final_train":    final_metrics,
            "log_transform":  True,
        }, f, indent=2)

    print(f"\nSaved -> {model_path}")
    print(f"Saved -> {features_path}")
    print(f"Saved -> {metrics_path}")
