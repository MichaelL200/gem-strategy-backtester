"""Price download from Yahoo Finance with a per-ticker CSV cache."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data/cache")
MAX_AGE_SECONDS = 12 * 3600
CASH = "USD"  # not downloaded: price 1.0 on every day (0% return)


def load_prices(tickers: list[str]) -> pd.DataFrame:
    """Daily adjusted close, one column per ticker (CASH is 1.0 on every day)."""
    prices = pd.DataFrame({t: _load(t) for t in tickers if t != CASH}).sort_index()
    if CASH in tickers:
        prices[CASH] = 1.0
    return prices[list(tickers)]


def _load(ticker: str) -> pd.Series:
    path = CACHE_DIR / f"{ticker}.csv"
    if path.exists() and time.time() - path.stat().st_mtime < MAX_AGE_SECONDS:
        try:
            return _read_cache(path)
        except (ValueError, TypeError, IndexError):
            pass  # damaged cache file: download again

    import yfinance as yf

    raw = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        raise ValueError(f"No price data for {ticker}")
    close = raw["Close"].squeeze().dropna().rename(ticker)
    close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    close = _tidy(close)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # write to a temporary file first so that parallel runs never mix up one file
    temp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    close.to_csv(temp)
    os.replace(temp, path)
    return close


def _read_cache(path: Path) -> pd.Series:
    close = pd.read_csv(path, index_col=0).iloc[:, 0]
    close.index = pd.to_datetime(close.index, format="%Y-%m-%d")  # fails if a row is not a date
    return _tidy(close.astype(float))


def _tidy(close: pd.Series) -> pd.Series:
    """Sorted, one price per day (Yahoo sometimes repeats a date)."""
    return close[~close.index.duplicated(keep="last")].sort_index()
