"""Pure backtest logic: every month hold the asset with the best return over the lookback window."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass(frozen=True)
class Result:
    equity: pd.Series  # strategy value per day, starts at 1.0
    assets: pd.DataFrame  # each asset held alone, starting at the strategy's value on its first day
    picks: pd.Series  # asset chosen at each month-end (decided at the close)
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float

    @property
    def drawdown(self) -> pd.Series:
        return self.equity / self.equity.cummax() - 1.0

    @property
    def start(self) -> pd.Timestamp:
        return self.equity.index[0]

    @property
    def end(self) -> pd.Timestamp:
        return self.equity.index[-1]


def momentum_table(prices: pd.DataFrame, lookback: int, skip: int = 0) -> pd.DataFrame:
    """Month-end momentum: return from `lookback` months ago to `skip` months ago.

    `prices` must be sorted and forward-filled. Each row only uses prices up to that month-end.
    """
    month_ends = prices.groupby(prices.index.to_period("M")).tail(1)
    return month_ends.shift(skip) / month_ends.shift(lookback) - 1.0


def run(
    prices: pd.DataFrame,
    lookback: int,
    skip: int = 0,
    start: pd.Timestamp | str | None = None,
    end: pd.Timestamp | str | None = None,
    common: bool = False,
) -> Result:
    """Backtest on daily prices (one column per asset).

    At each month-end the asset with the highest return from `lookback` months ago to
    `skip` months ago is chosen (skip=1 ignores the most recent month); it is held from
    the next trading day. Assets without a price at the start of the window are not
    eligible. The pick made on the last day of data is shown but not traded.

    Period (all optional):
    - default: trade from the first month-end at which at least one asset has enough history;
      assets join the ranking as soon as they have enough history of their own.
    - `common=True`: trade only from the first month-end at which every asset is eligible.
    - `start` / `end`: first pick at the first month-end on or after `start`; data after `end`
      is ignored. Prices before `start` are still used for the first signals (no look-ahead).
    """
    if lookback <= skip:
        raise ValueError("Lookback must be longer than the ignored months")
    prices = prices.sort_index().ffill()  # a missing day must not drop an asset from the ranking
    if end is not None:
        prices = prices.loc[: pd.Timestamp(end)]
    momentum = momentum_table(prices, lookback, skip).dropna(how="any" if common else "all")
    if start is not None:
        momentum = momentum.loc[momentum.index >= pd.Timestamp(start)]
    if momentum.empty:
        raise ValueError("Not enough price history for this lookback and period")
    picks = momentum.idxmax(axis=1)

    # A pick made at the close of day d earns the returns from day d+1 on.
    held = picks.reindex(prices.index).ffill().shift(1).dropna()
    returns = prices.pct_change(fill_method=None)
    column = held.map({name: i for i, name in enumerate(prices.columns)}).astype(int)
    daily = pd.Series(
        returns.to_numpy()[returns.index.get_indexer(held.index), column.to_numpy()],
        index=held.index,
    ).fillna(0.0)

    start = picks.index[0]
    equity = pd.concat([pd.Series({start: 1.0}), (1.0 + daily).cumprod()])
    if len(equity) < 3:
        raise ValueError("Not enough price history for this lookback")
    return _with_metrics(equity, _held_alone(prices.loc[start:], equity), picks)


def _held_alone(prices: pd.DataFrame, equity: pd.Series) -> pd.DataFrame:
    """Each asset held alone; an asset that starts later begins at the strategy's value that day."""
    strategy = equity.reindex(prices.index).ffill()
    lines = {}
    for name in prices.columns:
        first = prices[name].first_valid_index()
        if first is not None:
            lines[name] = prices[name] / prices[name][first] * strategy[first]
    return pd.DataFrame(lines)


def _with_metrics(equity: pd.Series, assets: pd.DataFrame, picks: pd.Series) -> Result:
    returns = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    volatility = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
    return Result(
        equity=equity,
        assets=assets,
        picks=picks,
        total_return=float(equity.iloc[-1] - 1.0),
        cagr=float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        volatility=volatility,
        sharpe=float(returns.mean() * TRADING_DAYS / volatility) if volatility else np.nan,
        max_drawdown=float((equity / equity.cummax() - 1.0).min()),
    )
