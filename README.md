# gem-strategy-backtester

A modular Python tool to backtest and analyze Global Equities Momentum (GEM) and custom momentum-based quantitative strategies.

## How GEM Works

Global Equities Momentum (GEM), developed by Gary Antonacci, is a dual-momentum quantitative model. The classic algorithm follows this step-by-step process:

1. **Define the Asset Palette:** The strategy monitors a predefined set of assets—typically US Equities (e.g., S&P 500), Non-US Equities (e.g., MSCI ACWI ex-US or MSCI EM), and a safe harbor asset like US Aggregate Bonds.
2. **Compare in a Lookback Window:** It evaluates the historical performance of the equity assets over a set timeframe (traditionally a 12-month window, often excluding the last month).
3. **Select the Winner:** For the upcoming rebalancing period, it picks the equity asset that had the best returns (Relative Momentum). If that top asset's return is negative or lower than the risk-free rate / T-Bills (Absolute Momentum), capital is instead allocated 100% into the safe harbor bonds.
4. **Repeat Periodically:** This evaluation and execution process is repeated at the end of every period (typically every month).

*Note: While this backtester allows you to adapt parameters (asset palettes, lookback windows, rebalancing frequencies), the classic parameters were mathematically demonstrated by Antonacci to be the most historically effective while maintaining strict operational simplicity.*

## Features

- **Automated Data Pipeline:** Downloads historical market data across multiple asset classes (Equities, Bonds, Commodities) from Yahoo Finance (yfinance library in Python).
- **Interactive UI:** Select assets, asset classes, and benchmarks directly from the interface.
- **Custom Strategy Parameters:** Easily adjust lookback periods, rebalancing frequencies, and asset allocation rules.

## UI Theme

Designed with a low-fatigue, high-contrast dark theme optimized for quant dashboards:
- **Background:** Charcoal (`#0E1117`)
- **Panels & Cards:** Dark Slate (`#1E232A`)
- **Accent & Gains:** Emerald Green (`#00C853`)