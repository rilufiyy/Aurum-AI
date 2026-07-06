#!/usr/bin/env python3
"""
Phase 1 - Data Ingestion
Fetches historical XAU/USD, USD/IDR, and UBS gold prices (IDR/gram).
Outputs individual CSVs and a merged CSV to data/raw/ for Phase 2.
"""

import os
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf

START_DATE = "2020-01-01"
END_DATE   = datetime.today().strftime("%Y-%m-%d")
RAW_DIR    = "data/raw"

os.makedirs(RAW_DIR, exist_ok=True)


def fetch_xauusd(start: str, end: str) -> pd.DataFrame:
    """XAU/USD gold futures daily close (COMEX GC=F)."""
    df = yf.download("GC=F", start=start, end=end, progress=False, auto_adjust=True)
    if df.empty:
        raise RuntimeError("yfinance returned empty data for GC=F")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Close"]].rename(columns={"Close": "xauusd"})
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    return df


def fetch_usdidr(start: str, end: str) -> pd.DataFrame:
    """USD/IDR daily close from forex market (USDIDR=X)."""
    df = yf.download("USDIDR=X", start=start, end=end, progress=False, auto_adjust=True)
    if df.empty:
        raise RuntimeError("yfinance returned empty data for USDIDR=X")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Close"]].rename(columns={"Close": "usdidr"})
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    return df



def fetch_ubs_historical(days: int = 1095) -> pd.DataFrame:
    """
    Fetches UBS gold sell price history from the ubslifestyle.com internal API.

    Endpoint : POST https://ubslifestyle.com/wp-admin/admin-ajax.php
    Payload  : action=get_harga_emas_hari_ini
               path=ajax/chart_interval_jual/GOLD/{days}

    Response format (per data point):
        [timestamp_ms, sell_price, sell_price, sell_price, buyback_price]
    """
    url     = "https://ubslifestyle.com/wp-admin/admin-ajax.php"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer":      "https://ubslifestyle.com/harga-buyback-hari-ini/",
    }
    payload = {
        "action": "get_harga_emas_hari_ini",
        "path":   f"ajax/chart_interval_jual/GOLD/{days}",
    }

    resp = requests.post(url, data=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    body = resp.json()

    if not body or not isinstance(body, list) or "data" not in body[0]:
        raise RuntimeError(f"Unexpected API response structure: {str(body)[:200]}")

    records = []
    for point in body[0]["data"]:
        try:
            date         = pd.Timestamp(point[0], unit="ms").normalize()
            sell_price   = float(point[1])
            buyback_price = float(point[4])
            records.append({
                "date":               date,
                "ubs_sell_idr":       sell_price,
                "ubs_buyback_idr":    buyback_price,
            })
        except (IndexError, ValueError, TypeError):
            continue

    if not records:
        raise RuntimeError("Parsed 0 records from UBS API response.")

    df = (
        pd.DataFrame(records)
        .drop_duplicates("date")
        .set_index("date")
        .sort_index()
    )
    df.index.name = "date"
    return df


def merge_datasets(
    xau: pd.DataFrame,
    idr: pd.DataFrame,
    ubs: pd.DataFrame,
) -> pd.DataFrame:
    """
    Inner-join on date. Only rows where all three sources have data are kept.
    Trading-day mismatches (weekends, local holidays) are dropped automatically.
    """
    df = xau.join(idr, how="inner").join(ubs, how="inner")
    df.dropna(inplace=True)

    df["implied_idr_per_gram"] = (df["xauusd"] / 31.1035) * df["usdidr"]
    df["ubs_premium_pct"]      = (
        (df["ubs_sell_idr"] - df["implied_idr_per_gram"])
        / df["implied_idr_per_gram"]
        * 100
    )

    return df


if __name__ == "__main__":
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Output directory: {RAW_DIR}\n")

    print("[1/3] Fetching XAU/USD (yfinance: GC=F)...")
    xau = fetch_xauusd(START_DATE, END_DATE)
    xau.to_csv(os.path.join(RAW_DIR, "xauusd.csv"))
    print(f"  {len(xau)} rows saved -> {RAW_DIR}/xauusd.csv\n")

    print("[2/3] Fetching USD/IDR (yfinance: USDIDR=X)...")
    idr = fetch_usdidr(START_DATE, END_DATE)
    idr.to_csv(os.path.join(RAW_DIR, "usdidr.csv"))
    print(f"  {len(idr)} rows saved -> {RAW_DIR}/usdidr.csv\n")

    print("[3/3] Fetching UBS historical prices (ubslifestyle.com API)...")
    ubs = fetch_ubs_historical(days=1095)
    ubs.to_csv(os.path.join(RAW_DIR, "ubs_prices.csv"))
    print(f"  {len(ubs)} rows saved -> {RAW_DIR}/ubs_prices.csv\n")

    print("Merging all datasets...")
    merged = merge_datasets(xau, idr, ubs)
    out_path = os.path.join(RAW_DIR, "merged_features.csv")
    merged.to_csv(out_path)
    print(f"  {len(merged)} rows saved -> {out_path}")

    print("\n--- Dataset Summary ---")
    print(merged.describe().to_string())

    print("\n--- Last 5 rows ---")
    print(merged.tail(5).to_string())

    avg_premium = merged["ubs_premium_pct"].mean()
    print(f"\nAverage UBS premium over spot (implied): {avg_premium:.2f}%")
    print("If this value is outside 2-15%, inspect the scraped prices for errors.")
