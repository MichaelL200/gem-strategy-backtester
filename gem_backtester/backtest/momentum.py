"""Momentum scoring: normal and volatility-adjusted, with outlier detection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from gem_backtester.backtest.base import BaseStrategy
from gem_backtester.backtest.metrics import TRADING_DAYS

MIN_OUTLIER_ASSETS = 4  # below this the median and spread of the scores mean nothing
MAD_SCALE = 0.6745  # makes the modified z-score comparable to a normal z-score
DEFAULT_OUTLIER_THRESHOLD = 3.5  # the usual cut-off for the modified z-score (Iglewicz & Hoaglin)


def momentum_table(
    prices: pd.DataFrame, lookback: int, skip: int = 0, volatility_adjusted: bool = False
) -> pd.DataFrame:
    """Month-end momentum: return from `lookback` months ago to `skip` months ago.

    With `volatility_adjusted` that return is divided by the standard deviation of the daily
    returns over the same window, so a smooth riser beats a wild one; an asset that never moves
    (cash) scores 0.

    `prices` must be sorted and forward-filled. Each row only uses prices up to that month-end.
    """
    month_ends = prices.groupby(prices.index.to_period("M")).tail(1)
    momentum = month_ends.shift(skip) / month_ends.shift(lookback) - 1.0
    if not volatility_adjusted:
        return momentum
    returns = prices.pct_change(fill_method=None)
    dates = month_ends.index
    volatility = pd.DataFrame(np.nan, index=dates, columns=prices.columns)
    for i in range(lookback, len(dates)):
        # the first day's return belongs to the period before the window
        volatility.iloc[i] = returns.loc[dates[i - lookback] : dates[i - skip]].iloc[1:].std()
    return (momentum / volatility).where(volatility != 0, momentum * 0.0)


def outlier_flags(momentum: pd.DataFrame, threshold: float | None, keep: int = 1) -> pd.DataFrame:
    """True where an asset's score is an unusually high outlier among the assets ranked that day.

    Uses the modified z-score, 0.6745 * (score - median) / MAD, where MAD is the median absolute
    deviation of the scores: unlike the mean and the standard deviation, they are hardly moved
    by the outliers themselves, so a +1156% score cannot hide itself. An asset is flagged when
    its z-score is above `threshold` (lower = stronger; 3.5 is the usual cut-off). Only the high
    side is flagged. Each row only uses that row's scores, so there is no look-ahead.

    Nothing is flagged on a day with fewer than MIN_OUTLIER_ASSETS ranked assets, or when more
    than half of the scores are equal (MAD = 0, no spread to measure). At most
    `ranked - keep` assets are flagged (the highest scores first), so `keep` always remain.
    """
    flags = pd.DataFrame(False, index=momentum.index, columns=momentum.columns)
    if threshold is None:
        return flags
    for date, row in momentum.iterrows():
        scores = row.dropna()
        if len(scores) < MIN_OUTLIER_ASSETS:
            continue
        median = scores.median()
        mad = (scores - median).abs().median()
        if mad == 0:
            continue
        z = MAD_SCALE * (scores - median) / mad
        flagged = z[z > threshold].sort_values(ascending=False).index[: len(scores) - keep]
        flags.loc[date, flagged] = True
    return flags


class MomentumStrategy(BaseStrategy):
    """Ranks assets by their return over a lookback window, optionally volatility-adjusted.

    This is the built-in strategy: it implements :class:`BaseStrategy` and is what
    :func:`~gem_backtester.backtest.engine.run` uses by default via its
    ``volatility_adjusted`` parameter.

    Args:
        lookback: Number of months to look back for the momentum signal.
        skip: Number of most-recent months to ignore (skip=1 avoids the reversal effect).
        volatility_adjusted: If True, divide the return by the daily-return volatility
            over the same window, so a smooth riser beats a wild one.
    """

    def __init__(self, lookback: int, skip: int = 0, volatility_adjusted: bool = False) -> None:
        self.lookback = lookback
        self.skip = skip
        self.volatility_adjusted = volatility_adjusted

    def compute_scores(self, prices: pd.DataFrame) -> pd.DataFrame:
        return momentum_table(prices, self.lookback, self.skip, self.volatility_adjusted)
