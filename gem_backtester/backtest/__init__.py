"""Backtest package: momentum strategy engine with a pluggable BaseStrategy interface.

Public API (unchanged from the previous single-module layout):

    from gem_backtester.backtest import run, Result, momentum_table, outlier_flags
    from gem_backtester.backtest import BaseStrategy, MomentumStrategy
    from gem_backtester.backtest import TRADING_DAYS, MIN_OUTLIER_ASSETS, DEFAULT_OUTLIER_THRESHOLD
"""

from gem_backtester.backtest.base import BaseStrategy
from gem_backtester.backtest.engine import run
from gem_backtester.backtest.metrics import TRADING_DAYS, Result, compute_metrics
from gem_backtester.backtest.momentum import (
    DEFAULT_OUTLIER_THRESHOLD,
    MIN_OUTLIER_ASSETS,
    MomentumStrategy,
    momentum_table,
    outlier_flags,
)

__all__ = [
    # core runner
    "run",
    # result & metrics
    "Result",
    "compute_metrics",
    # scoring
    "momentum_table",
    "outlier_flags",
    # strategy interface
    "BaseStrategy",
    "MomentumStrategy",
    # constants
    "TRADING_DAYS",
    "MIN_OUTLIER_ASSETS",
    "DEFAULT_OUTLIER_THRESHOLD",
]
