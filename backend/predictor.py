import json
import os
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import requests
import yfinance as yf

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH    = os.path.join(BASE_DIR, "model", "model.pkl")
FEATURES_PATH = os.path.join(BASE_DIR, "model", "feature_names.json")

_model    = None
_features = None


def get_model():
    global _model, _features
    if _model is None:
        _model    = joblib.load(MODEL_PATH)
        _features = json.load(open(FEATURES_PATH))
    return _model, _features


def fetch_market_data(days: int = 45) -> pd.DataFrame:
    end   = datetime.today()
    start = end - timedelta(days=days * 2)

    xau = yf.download("GC=F", start=start, end=end, progress=False, auto_adjust=True)
    idr = yf.download("USDIDR=X", start=start, end=end, progress=False, auto_adjust=True)

    for df in [xau, idr]:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

    xau = xau[["Close"]].rename(columns={"Close": "xauusd"})
    idr = idr[["Close"]].rename(columns={"Close": "usdidr"})

    xau.index = pd.to_datetime(xau.index).tz_localize(None)
    idr.index = pd.to_datetime(idr.index).tz_localize(None)

    return xau.join(idr, how="inner").tail(days)


def fetch_ubs_data(days: int = 45) -> pd.DataFrame:
    url     = "https://ubslifestyle.com/wp-admin/admin-ajax.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":    "https://ubslifestyle.com/harga-buyback-hari-ini/",
    }
    payload = {
        "action": "get_harga_emas_hari_ini",
        "path":   f"ajax/chart_interval_jual/GOLD/{days}",
    }

    resp = requests.post(url, data=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    records = [
        {
            "date":             pd.Timestamp(p[0], unit="ms").normalize(),
            "ubs_sell_idr":     float(p[1]),
            "ubs_buyback_idr":  float(p[4]),
        }
        for p in body[0]["data"]
    ]

    df = pd.DataFrame(records).drop_duplicates("date").set_index("date").sort_index()
    return df.tail(days)


def build_features(market: pd.DataFrame, ubs: pd.DataFrame) -> pd.DataFrame:
    df = market.join(ubs[["ubs_sell_idr", "ubs_buyback_idr"]], how="inner").sort_index()

    df["implied_x_1g"]     = (df["xauusd"] / 31.1035) * df["usdidr"]
    df["ubs_premium_ratio"] = df["ubs_sell_idr"] / df["implied_x_1g"]

    for lag in [1, 2, 3, 5, 7]:
        df[f"xauusd_lag{lag}"]        = df["xauusd"].shift(lag)
        df[f"usdidr_lag{lag}"]        = df["usdidr"].shift(lag)
        df[f"premium_ratio_lag{lag}"] = df["ubs_premium_ratio"].shift(lag)

    for window in [5, 10, 20]:
        df[f"xauusd_ma{window}"]        = df["xauusd"].rolling(window).mean()
        df[f"usdidr_ma{window}"]        = df["usdidr"].rolling(window).mean()
        df[f"premium_ratio_ma{window}"] = df["ubs_premium_ratio"].rolling(window).mean()

    df["xauusd_pct_change"] = df["xauusd"].pct_change()
    df["usdidr_pct_change"] = df["usdidr"].pct_change()
    df["day_of_week"]       = df.index.dayofweek
    df["month"]             = df.index.month

    df.dropna(inplace=True)
    return df


def predict_current() -> dict:
    model, features = get_model()

    market = fetch_market_data(days=45)
    ubs    = fetch_ubs_data(days=45)
    df     = build_features(market, ubs)

    if df.empty:
        raise RuntimeError("Not enough data to generate features for prediction.")

    latest         = df.iloc[[-1]]
    X              = latest[features].values
    pred_ratio     = float(model.predict(X)[0])
    implied        = float(latest["implied_x_1g"].iloc[0])
    price          = pred_ratio * implied
    premium        = (pred_ratio - 1.0) * 100

    actual         = int(latest["ubs_sell_idr"].iloc[0])
    error_idr      = round(price) - actual
    error_pct      = round((price - actual) / actual * 100, 2)

    return {
        "date":                  str(latest.index[0].date()),
        "predicted_price_idr":   round(price),
        "actual_ubs_price_idr":  actual,
        "xauusd_live":           round(float(latest["xauusd"].iloc[0]), 2),
        "usdidr_live":           round(float(latest["usdidr"].iloc[0]), 2),
        "implied_spot_idr":      round(implied),
        "premium_pct":           round(premium, 2),
        "prediction_error_idr":  error_idr,
        "prediction_error_pct":  error_pct,
    }


def get_history(days: int = 30) -> list[dict]:
    market = fetch_market_data(days=days + 10)
    ubs    = fetch_ubs_data(days=days + 10)

    df = market.join(ubs[["ubs_sell_idr"]], how="inner").tail(days)

    result = []
    for date, row in df.iterrows():
        implied = (row["xauusd"] / 31.1035) * row["usdidr"]
        result.append({
            "date":             str(date.date()),
            "ubs_sell_idr":     row["ubs_sell_idr"],
            "xauusd":           round(row["xauusd"], 2),
            "usdidr":           round(row["usdidr"], 2),
            "implied_spot_idr": round(implied),
        })
    return result


def forecast_budget(budget_idr: float, weight_gram: float = 1.0) -> dict:
    model, features = get_model()

    market = fetch_market_data(days=45)
    ubs    = fetch_ubs_data(days=45)
    df     = build_features(market, ubs)

    if df.empty:
        raise RuntimeError("Not enough data to generate forecast.")

    last_row      = df.iloc[[-1]]
    pred_ratio    = float(model.predict(last_row[features].values)[0])
    current_price = round(pred_ratio * float(last_row["implied_x_1g"].iloc[0]))
    current_units = budget_idr / (current_price * weight_gram)

    xau_last5 = df["xauusd"].tail(5)
    idr_last5 = df["usdidr"].tail(5)
    xau_trend = (xau_last5.iloc[-1] - xau_last5.iloc[0]) / 5
    idr_trend = (idr_last5.iloc[-1] - idr_last5.iloc[0]) / 5

    forecast   = []
    last_row   = df.iloc[-1].copy()
    best_price = current_price
    best_date  = str(df.index[-1].date())

    for day_offset in range(1, 8):
        future_date = df.index[-1] + timedelta(days=day_offset)
        if future_date.weekday() >= 5:
            continue

        projected_xau = float(last_row["xauusd"]) + xau_trend * day_offset
        projected_idr = float(last_row["usdidr"]) + idr_trend * day_offset

        future_row = last_row.copy()
        future_row["xauusd"]           = projected_xau
        future_row["usdidr"]           = projected_idr
        future_row["implied_x_1g"]     = (projected_xau / 31.1035) * projected_idr
        future_row["xauusd_pct_change"] = (projected_xau - float(last_row["xauusd"])) / float(last_row["xauusd"])
        future_row["usdidr_pct_change"] = (projected_idr - float(last_row["usdidr"])) / float(last_row["usdidr"])

        X              = future_row[features].values.reshape(1, -1)
        future_implied = (projected_xau / 31.1035) * projected_idr
        pred_ratio     = float(model.predict(X)[0])
        pred_price     = round(pred_ratio * future_implied)
        units       = budget_idr / (pred_price * weight_gram)

        if pred_price < best_price:
            best_price = pred_price
            best_date  = str(future_date.date())

        forecast.append({
            "date":                 str(future_date.date()),
            "predicted_price_idr":  pred_price,
            "units_affordable":     round(units, 4),
            "is_best_day":          False,
        })

    for f in forecast:
        if f["date"] == best_date:
            f["is_best_day"] = True

    recommendation = (
        f"Berdasarkan tren 5 hari terakhir, harga UBS emas {weight_gram}g "
        f"diperkirakan paling rendah pada {best_date} "
        f"di sekitar Rp{best_price:,.0f}. "
        f"Dengan budget Rp{budget_idr:,.0f}, kamu bisa membeli sekitar "
        f"{round(budget_idr / (best_price * weight_gram), 4)} unit."
    )

    return {
        "budget_idr":               budget_idr,
        "weight_gram":              weight_gram,
        "current_price_idr":        current_price,
        "current_units_affordable": round(current_units, 4),
        "forecast":                 forecast,
        "recommendation":           recommendation,
    }
