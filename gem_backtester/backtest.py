"""Pure backtest logic: every rebalancing period hold the asset with the best return over the lookback window."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass(frozen=True)
class Result:
    equity: pd.Series  # strategy value per day, starts at 1.0
    assets: pd.DataFrame  # each asset held alone, starting at the strategy's value on its first day
    picks: pd.Series  # tickers chosen at each rebalance date (list per date, best first)
    composition: pd.DataFrame  # share of each held asset in the portfolio per day (rows sum to 1)
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
    rebalance: int = 1,
    top_n: int = 1,
) -> Result:
    """Backtest on daily prices (one column per asset).

    Every `rebalance` months (counted in month-ends, 1 = monthly) the `top_n` assets with the
    highest return from `lookback` months ago to `skip` months ago are chosen (skip=1 ignores the
    most recent month). The portfolio is set to equal weights (1/n each) at that close and held
    from the next trading day until the next rebalance; between rebalances the weights drift with
    prices. Assets without a price at the start of the window are not eligible; if fewer than
    `top_n` are eligible, only those are held. The picks made on the last day of data are shown
    but not traded.

    Period (all optional):
    - default: trade from the first month-end at which at least one asset has enough history;
      assets join the ranking as soon as they have enough history of their own.
    - `common=True`: trade only from the first month-end at which every asset is eligible.
    - `start` / `end`: the strategy earns from the first trading day on or after `start` (the
      portfolio is set at the close before it, from the last month-end signal known by then) up
      to `end`; data after `end` is ignored. Prices before `start` are still used for the first
      signals (no look-ahead). If there is no signal before `start`, trading starts at the first
      month-end on or after it.

    The first pick is always the first rebalance; later ones follow every `rebalance` month-ends.
    """
    if lookback <= skip:
        raise ValueError("Lookback must be longer than the ignored months")
    if rebalance < 1:
        raise ValueError("Rebalancing period must be at least 1 month")
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    prices = prices.sort_index().ffill()  # a missing day must not drop an asset from the ranking
    if end is not None:
        prices = prices.loc[: pd.Timestamp(end)]
    momentum = momentum_table(prices, lookback, skip).dropna(how="any" if common else "all")
    bought = None  # when the first position is bought, if not at the signal's own close
    if start is not None:
        first_day = prices.index[prices.index >= pd.Timestamp(start)][:1]
        known = momentum.index[momentum.index < first_day[0]] if len(first_day) else []
        if len(known):  # a signal exists before the period: hold it from the period's first day
            momentum = momentum.loc[momentum.index >= known[-1]]
            bought = prices.index[prices.index < first_day[0]][-1]
        else:
            momentum = momentum.loc[momentum.index >= pd.Timestamp(start)]
    if momentum.empty:
        raise ValueError("Not enough price history for this lookback and period")

    picks = momentum.iloc[::rebalance].apply(lambda row: list(row.dropna().nlargest(top_n).index), axis=1)
    if bought is not None:  # the portfolio is set at the close before the first day of the period
        picks.index = pd.DatetimeIndex([bought, *picks.index[1:]])
    start = picks.index[0]

    # A pick made at the close of day d is bought at that close and earns from day d+1 on.
    # Between rebalances nothing is traded: each asset's value is weight * price / price at d.
    weights = pd.DataFrame(0.0, index=picks.index, columns=prices.columns)
    for date, tickers in picks.items():
        weights.loc[date, tickers] = 1.0 / len(tickers)
    days = prices.index[prices.index > start]
    period = pd.Series(picks.index, picks.index).reindex(prices.index).ffill().shift(1)[days]
    value = weights.loc[period].to_numpy() * prices.loc[days].to_numpy() / prices.loc[period].to_numpy()
    growth = pd.Series(np.nansum(value, axis=1), index=days)  # relative to the last rebalance
    carried = growth.groupby(period).last().cumprod().shift(fill_value=1.0)  # value at rebalance
    equity = pd.concat([pd.Series({start: 1.0}), growth * carried.reindex(period).to_numpy()])
    shares = pd.DataFrame(np.nan_to_num(value) / growth.to_numpy()[:, None], days, prices.columns)
    composition = pd.concat([weights.iloc[[0]], shares])
    composition = composition.loc[:, composition.gt(0).any()]  # only assets that were held
    if len(equity) < 3:
        raise ValueError("Not enough price history for this lookback")
    return _with_metrics(equity, _held_alone(prices.loc[start:], equity), picks, composition)


def _held_alone(prices: pd.DataFrame, equity: pd.Series) -> pd.DataFrame:
    """Each asset held alone; an asset that starts later begins at the strategy's value that day."""
    strategy = equity.reindex(prices.index).ffill()
    lines = {}
    for name in prices.columns:
        first = prices[name].first_valid_index()
        if first is not None:
            lines[name] = prices[name] / prices[name][first] * strategy[first]
    return pd.DataFrame(lines)


def _with_metrics(
    equity: pd.Series, assets: pd.DataFrame, picks: pd.Series, composition: pd.DataFrame
) -> Result:
    returns = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    volatility = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
    return Result(
        equity=equity,
        assets=assets,
        picks=picks,
        composition=composition,
        total_return=float(equity.iloc[-1] - 1.0),
        cagr=float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        volatility=volatility,
        sharpe=float(returns.mean() * TRADING_DAYS / volatility) if volatility else np.nan,
        max_drawdown=float((equity / equity.cummax() - 1.0).min()),
    )
