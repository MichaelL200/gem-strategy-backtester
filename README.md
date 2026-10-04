# gem-strategy-backtester

A modular Python tool to backtest and analyze Global Equities Momentum (GEM) and custom momentum-based quantitative strategies.

🚀 **Live demo:** [gem-strategy-backtester.streamlit.app](https://gem-strategy-backtester.streamlit.app)

## How GEM Works

Global Equities Momentum (GEM), developed by Gary Antonacci, is a dual-momentum quantitative model. The classic algorithm follows this step-by-step process:

1. **Define the Asset Palette:** The strategy monitors a predefined set of assets—typically US Equities (e.g., S&P 500), Non-US Equities (e.g., MSCI ACWI ex-US or MSCI EM), and a safe harbor asset like US Aggregate Bonds.
2. **Compare in a Lookback Window:** It evaluates the historical performance of the equity assets over a set timeframe (traditionally a 12-month window, often excluding the last month).
3. **Select the Winner:** For the upcoming rebalancing period, it picks the equity asset that had the best returns (Relative Momentum). To minimize drawdowns it is good to include a safe-heaven asset in the assets.
4. **Repeat Periodically:** This evaluation and execution process is repeated at the end of every rebalancing period (typically every month).

*Note: While this backtester allows you to adapt parameters (asset palettes, lookback windows, ignored months), the classic parameters were mathematically demonstrated by Antonacci to be the most historically effective while maintaining strict operational simplicity.*

## Features

- **Automated Data Pipeline:** Downloads historical market data across multiple asset classes (Equities, Commodities, Real Estate, Bonds and Cash; **Cash (USD)** is plain dollars with 0% return) from Yahoo Finance (yfinance library in Python).
- **Interactive UI:** The sidebar has four sections: **1 · Assets**, **2 · Lookback window**, **3 · Rebalancing** and **4 · Backtest period**. The chart compares the strategy with each asset held alone.
- **Custom Strategy Parameters:** Adjust the asset list (**Select all** / **Clear** buttons), the lookback window, the ignored months and the rebalancing period (every 1 to 12 months; monthly by default). The first pick is the first rebalance, and the chosen asset is held until the next one. **Hold top N assets** (1 to the number of selected assets) holds the N best in equal weights (1/N) set at each rebalance; between rebalances the weights drift with prices. With N equal to the number of assets, momentum is ignored (an equal-weight portfolio).
  Defaults: MSCI World (DM), Gold, Bonds 7-10Y and Bonds 0-1Y; look back 12 months, ignore the last 1, so momentum is measured over **11 months**. The sidebar shows the window length.
- **Backtest period:** *All available data* (assets join the ranking once they have enough history), *Common period* (default; starts when every selected asset can be ranked) or *Custom* (pick from/to dates). Prices before a custom start are still used for the first signals. The duration of the backtest (e.g. `13 years 8 months`) is shown with the results, and a *Data available per asset* table shows when each asset can first be ranked.

## Getting Started

Requires Python 3.x+.

1. **Clone the repository**
```sh
   git clone https://github.com/MichaelL200/gem-strategy-backtester
   cd gem-strategy-backtester
```

2. **Create and activate a virtual environment**

   **Linux / macOS**
   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows (PowerShell)**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1   # CMD: .venv\Scripts\activate.bat
   ```

3. **Install dependencies**
```sh
   pip install -r requirements.txt
```

4. **Run the app**
```sh
   streamlit run app.py
```

The app opens in your browser at <http://localhost:8501>. If it doesn't, open that address manually. Press `Ctrl+C` in the terminal to stop it.

Run the tests with `pytest`.

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

The app follows your system's light/dark setting by default. To manually change it, open the ⋮ menu (top right) and select **System**, **Light** or **Dark**.

### 🌙 Dark Mode

| Element | Color |
|---|---|
| **Background** (Charcoal) | ![#0E1117](https://img.shields.io/badge/-0E1117-0E1117?style=for-the-badge) |
| **Panels & Cards** (Dark Slate) | ![#1E232A](https://img.shields.io/badge/-1E232A-1E232A?style=for-the-badge) |
| **Accent & Gains** (Emerald Green) | ![#00C853](https://img.shields.io/badge/-00C853-00C853?style=for-the-badge) |

### ☀️ Light Mode

| Element | Color |
|---|---|
| **Background** (White) | ![#FFFFFF](https://img.shields.io/badge/-FFFFFF-FFFFFF?style=for-the-badge) |
| **Panels & Cards** (Light Gray) | ![#F0F2F6](https://img.shields.io/badge/-F0F2F6-F0F2F6?style=for-the-badge) |
| **Accent & Gains** (Emerald Green) | ![#00A344](https://img.shields.io/badge/-00A344-00A344?style=for-the-badge) |
