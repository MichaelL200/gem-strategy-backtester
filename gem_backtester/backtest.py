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


def run(prices: pd.DataFrame, lookback: int, skip: int = 0) -> Result:
    """Backtest on daily prices (one column per asset), using all available data.

    At each month-end the asset with the highest return from `lookback` months ago to
    `skip` months ago is chosen (skip=1 ignores the most recent month); it is held from
    the next trading day. Assets without a price at the start of the window are not
    eligible. The pick made on the last day of data is shown but not traded.
    """
    if lookback <= skip:
        raise ValueError("Lookback must be longer than the ignored months")
    prices = prices.sort_index().ffill()  # a missing day must not drop an asset from the ranking
    month_ends = prices.groupby(prices.index.to_period("M")).tail(1)
    momentum = (month_ends.shift(skip) / month_ends.shift(lookback) - 1.0).dropna(how="all")
    if momentum.empty:
        raise ValueError("Not enough price history for this lookback")
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
