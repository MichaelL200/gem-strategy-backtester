# gem-strategy-backtester

A modular Python tool to backtest and analyze Global Equities Momentum (GEM) and custom momentum-based quantitative strategies.

## How GEM Works

Global Equities Momentum (GEM), developed by Gary Antonacci, is a dual-momentum quantitative model. The classic algorithm follows this step-by-step process:

1. **Define the Asset Palette:** The strategy monitors a predefined set of assets—typically US Equities (e.g., S&P 500), Non-US Equities (e.g., MSCI ACWI ex-US or MSCI EM), and a safe harbor asset like US Aggregate Bonds.
2. **Compare in a Lookback Window:** It evaluates the historical performance of the equity assets over a set timeframe (traditionally a 12-month window, often excluding the last month).
3. **Select the Winner:** For the upcoming rebalancing period, it picks the equity asset that had the best returns (Relative Momentum). To minimize drawdowns it is good to include a safe-heaven asset in the assets.
4. **Repeat Periodically:** This evaluation and execution process is repeated at the end of every rebalancing period (typically every month).

*Note: While this backtester allows you to adapt parameters (asset palettes, lookback windows, ignored months), the classic parameters were mathematically demonstrated by Antonacci to be the most historically effective while maintaining strict operational simplicity.*

## Features

- **Automated Data Pipeline:** Downloads historical market data across multiple asset classes (Equities, Commodities, Bonds and Cash) from Yahoo Finance (yfinance library in Python).
- **Interactive UI:** The sidebar has four sections: **1 · Assets**, **2 · Lookback window**, **3 · Rebalancing** and **4 · Backtest period**. The chart compares the strategy with each asset held alone.
- **Custom Strategy Parameters:** Adjust the asset list, the lookback window, the ignored months and the rebalancing period (every 1 to 12 months; monthly by default). The first pick is the first rebalance, and the chosen asset is held until the next one.
  Defaults: MSCI World, Gold, Bonds 7-10Y and Bonds 0-1Y; look back 12 months, ignore the last 1, so momentum is measured over **11 months**. The sidebar shows the window length.
- **Backtest period:** *All available data* (assets join the ranking once they have enough history), *Common period* (starts when every selected asset can be ranked) or *Custom* (pick from/to dates). Prices before a custom start are still used for the first signals. The duration of the backtest (e.g. `13 years 8 months`) is shown with the results, and a *Data available per asset* table shows when each asset can first be ranked.

## Getting Started

```bash
pip install -r requirements.txt
streamlit run app.py
pytest
```

## Structure

```
app.py                  # Streamlit UI
gem_backtester/
├── assets.py           # Selectable assets by category (name -> ETF ticker); add new ones here
├── data.py             # Yahoo Finance download + CSV cache (data/cache/)
├── periods.py          # Period modes, durations ("11 months"), data availability
└── backtest.py         # Strategy and metrics (pure logic, no I/O)
tests/                  # pytest
```

## UI Theme

Designed with a low-fatigue, high-contrast dark theme optimized for quant dashboards:
- **Background:** Charcoal (`#0E1117`)
- **Panels & Cards:** Dark Slate (`#1E232A`)
- **Accent & Gains:** Emerald Green (`#00C853`)
