"""Backtest-period helpers: period modes, human-readable durations, data availability."""

from __future__ import annotations

import pandas as pd
from dateutil.relativedelta import relativedelta

from gem_backtester.backtest import momentum_table

ALL = "All available data"
COMMON = "Common period"
CUSTOM = "Custom"
MODES = (ALL, COMMON, CUSTOM)


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"


def window_months(lookback: int, skip: int) -> int:
    """Length of the window over which momentum is measured (12 back, ignore 1 -> 11)."""
    return lookback - skip


def window_text(lookback: int, skip: int) -> str:
    return _plural(window_months(lookback, skip), "month")


def duration_text(start: pd.Timestamp | str, end: pd.Timestamp | str) -> str:
    """'13 years 8 months', '11 months'; days only when shorter than a month."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if end < start:
        raise ValueError("End is before start")
    delta = relativedelta(end.to_pydatetime(), start.to_pydatetime())
    parts = []
    if delta.years:
        parts.append(_plural(delta.years, "year"))
    if delta.months:
        parts.append(_plural(delta.months, "month"))
    return " ".join(parts) if parts else _plural(delta.days, "day")


def availability(prices: pd.DataFrame, lookback: int, skip: int = 0) -> pd.DataFrame:
    """Per asset: first price date and first month-end at which it can be ranked."""
    prices = prices.sort_index().ffill()
    momentum = momentum_table(prices, lookback, skip)
    return pd.DataFrame(
        {
            "First price": {c: prices[c].first_valid_index() for c in prices.columns},
            "Ranked from": {c: momentum[c].first_valid_index() for c in prices.columns},
        }
    )
