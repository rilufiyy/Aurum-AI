#!/usr/bin/env python3
"""
Phase 1 - Data Ingestion
Fetches historical XAU/USD, USD/IDR, and UBS gold prices (IDR/gram).
Outputs individual CSVs and a merged CSV to data/raw/ for Phase 2.
"""

import os
import time
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup

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


def _parse_idr_price(raw: str) -> float:
    """
    Clean IDR price strings to float.
    Handles formats: '1.050.000', '1,050,000', '1050000'
    """
    cleaned = raw.replace(".", "").replace(",", "").strip()
    return float(cleaned)


def scrape_ubs_prices(max_pages: int = 60) -> pd.DataFrame:
    """
    Scrapes UBS 1-gram gold price history (IDR) from harga-emas.org.

    Source URL: https://harga-emas.org/history/ubs/
    The site paginates via ?p=N. If the layout ever changes, inspect
    the table HTML at that URL and adjust the column index (cols[0]=date,
    cols[1]=buy price) accordingly.
    """
    BASE_URL = "https://harga-emas.org/history/ubs/"
    HEADERS  = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    }

    records = []

    for page in range(1, max_pages + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}?p={page}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  Request failed on page {page}: {exc}")
            break

        soup  = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table")

        if table is None:
            print(f"  No <table> found on page {page}. Pagination complete.")
            break

        rows = table.find_all("tr")[1:]
        if not rows:
            break

        page_records = 0
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 2:
                continue
            try:
                date  = pd.to_datetime(cols[0], dayfirst=True)
                price = _parse_idr_price(cols[1])
                records.append({"date": date, "ubs_idr_per_gram": price})
                page_records += 1
            except (ValueError, IndexError):
                continue

        print(f"  Page {page}: {page_records} rows parsed")

        if page_records == 0:
            break

        time.sleep(0.8)

    if not records:
        raise RuntimeError(
            "Scraped 0 UBS records. "
            "Open https://harga-emas.org/history/ubs/ in a browser, "
            "inspect the table HTML, and update the column indices."
        )

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
        (df["ubs_idr_per_gram"] - df["implied_idr_per_gram"])
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

    print("[3/3] Scraping UBS prices (harga-emas.org)...")
    ubs = scrape_ubs_prices()
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
