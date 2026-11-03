"""Result dataclass and performance metrics computed from an equity curve."""

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
    excluded: pd.Series  # tickers dropped as top outliers at each rebalance date (empty list if none)
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    calmar: float
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


def compute_metrics(
    equity: pd.Series,
    assets: pd.DataFrame,
    picks: pd.Series,
    composition: pd.DataFrame,
    excluded: pd.Series,
) -> Result:
    """Build a Result from an equity curve and the supporting series."""
    returns = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    volatility = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
    downside_dev = float(np.sqrt((np.minimum(0, returns) ** 2).mean()) * np.sqrt(TRADING_DAYS))

    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    max_drawdown = float((equity / equity.cummax() - 1.0).min())

    return Result(
        equity=equity,
        assets=assets,
        picks=picks,
        composition=composition,
        excluded=excluded,
        total_return=float(equity.iloc[-1] - 1.0),
        cagr=cagr,
        volatility=volatility,
        sharpe=float(returns.mean() * TRADING_DAYS / volatility) if volatility else np.nan,
        sortino=float(returns.mean() * TRADING_DAYS / downside_dev) if downside_dev else np.nan,
        calmar=float(cagr / -max_drawdown) if max_drawdown < 0 else np.nan,
        max_drawdown=max_drawdown,
    )
