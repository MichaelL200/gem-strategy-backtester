"""Backtest package: momentum strategy engine with a pluggable BaseStrategy interface.

Public API (unchanged from the previous single-module layout):

    from backtest import run, Result, momentum_table, outlier_flags
    from backtest import BaseStrategy, MomentumStrategy
    from backtest import TRADING_DAYS, MIN_OUTLIER_ASSETS, DEFAULT_OUTLIER_THRESHOLD
"""

from backtest.base import BaseStrategy
from backtest.engine import run
from backtest.metrics import TRADING_DAYS, Result, compute_metrics
from backtest.momentum import (
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
