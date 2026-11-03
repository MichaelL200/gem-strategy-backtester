"""Abstract base class for quantitative trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """Interface for a scoring strategy used by the backtest engine.

    Subclasses implement :meth:`compute_scores` to return a month-end DataFrame
    of scores (one column per asset). The engine picks the top-N assets by score
    at each rebalance date. NaN means the asset is not eligible that month.

    Example::

        class MyStrategy(BaseStrategy):
            def compute_scores(self, prices: pd.DataFrame) -> pd.DataFrame:
                # 12-month return, skip most recent month
                month_ends = prices.groupby(prices.index.to_period("M")).tail(1)
                return month_ends.shift(1) / month_ends.shift(12) - 1.0
    """

    @abstractmethod
    def compute_scores(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return month-end scores for each asset (higher = more attractive).

        Args:
            prices: Daily adjusted-close prices, sorted ascending, forward-filled.

        Returns:
            DataFrame indexed by month-end dates with the same columns as
            ``prices``. NaN indicates the asset is not eligible at that date.
            Each row must only use price data up to that date (no look-ahead).
        """
