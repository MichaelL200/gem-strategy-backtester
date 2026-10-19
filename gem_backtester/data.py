"""Price download from Yahoo Finance with a per-ticker CSV cache."""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path

import pandas as pd

from gem_backtester.assets import ASSETS

CACHE_DIR = Path("data/cache")
MAX_AGE_SECONDS = 12 * 3600
CASH = "USD"  # not downloaded: price 1.0 on every day (0% return)
CURRENCIES = ("USD", "EUR", "GBP", "PLN", "CHF", "JPY", "CAD", "AUD")  # the ones to choose from
CASH_ONLY_START = "2000-01-01"  # first day when only cash is chosen: there is no price history
PENCE = {"GBp": "GBP", "GBX": "GBP"}  # London quotes in a hundredth of a pound


def load_prices(tickers: list[str], currency: str = "USD") -> pd.DataFrame:
    """Daily adjusted close in `currency`, one column per ticker (CASH is 1.0 on every day).

    Every ticker is converted from the currency it is quoted in (see `_quote_currency`) with the
    daily rate Yahoo gives as "<currency>=X" (units of the currency per 1 USD, e.g. EUR=X), so the
    returns include the exchange rate. Days before the first rate are dropped. The tickers whose
    currency could not be found are taken as USD and listed in `prices.attrs["unknown_currency"]`.
    """
    if currency not in CURRENCIES:
        raise ValueError(f"Unknown currency {currency}")
    prices = pd.DataFrame({t: _load(t) for t in tickers if t != CASH}).sort_index()
    if CASH in tickers:
        if prices.empty:  # cash alone: no price history to take the days from
            days = pd.bdate_range(CASH_ONLY_START, pd.Timestamp.today().normalize())
            prices = pd.DataFrame(index=days)
        prices[CASH] = 1.0
    prices = prices[list(tickers)]
    rates: dict[str, pd.Series] = {}  # per currency: units per 1 USD on the days of `prices`

    def rate(code: str) -> pd.Series | float:
        if code == "USD":
            return 1.0
        if code not in rates:
            rates[code] = _load(f"{code}=X").reindex(prices.index, method="ffill")  # no look-ahead
        return rates[code]

    unknown = []
    for ticker in prices.columns:
        quote = _quote_currency(ticker)
        if quote is None:
            unknown.append(ticker)
            quote = "USD"
        code, scale = (PENCE[quote], 0.01) if quote in PENCE else (quote, 1.0)
        if code != currency:
            prices[ticker] = prices[ticker] * scale * rate(currency) / rate(code)
        elif scale != 1.0:
            prices[ticker] = prices[ticker] * scale
    prices = prices.dropna(how="all")
    prices.attrs["unknown_currency"] = unknown
    return prices


def _quote_currency(ticker: str) -> str | None:
    """The currency a ticker is quoted in (the built-in ones are in USD), None if unknown."""
    if ticker in ASSETS.values():
        return "USD"
    path = CACHE_DIR / f"{ticker}.currency"
    if path.exists() and re.fullmatch(r"[A-Za-z]{3}", path.read_text().strip()):
        return path.read_text().strip()
    try:
        import yfinance as yf

        found = yf.Ticker(ticker).fast_info["currency"]
    except Exception:
        return None
    if not isinstance(found, str) or not re.fullmatch(r"[A-Za-z]{3}", found):
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(found)
    return found


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
