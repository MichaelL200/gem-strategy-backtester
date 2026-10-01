"""Price download from Yahoo Finance with a per-ticker CSV cache."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data/cache")
MAX_AGE_SECONDS = 12 * 3600


def load_prices(tickers: list[str]) -> pd.DataFrame:
    """Daily adjusted close, one column per ticker."""
    return pd.DataFrame({t: _load(t) for t in tickers}).sort_index()


def _load(ticker: str) -> pd.Series:
    path = CACHE_DIR / f"{ticker}.csv"
    if path.exists() and time.time() - path.stat().st_mtime < MAX_AGE_SECONDS:
        return pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]

    import yfinance as yf

    raw = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        raise ValueError(f"No price data for {ticker}")
    close = raw["Close"].squeeze().dropna().rename(ticker)
    close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    close.to_csv(path)
    return close
