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

## Architecture

The project follows a **layered (hexagonal / ports-and-adapters) architecture** with a **ViewModel-style presentation layer**. All investment logic lives in a pure, I/O-free core, so it can be tested without network access, files or a UI.

```
Streamlit Views ──► ViewModels ──► Application services ──► Domain (pure logic)
                                          │
                                          ▼
                                   Ports (interfaces)
                                          ▲
                                          │
                       Infrastructure adapters (Yahoo Finance, CSV cache)
```

Dependencies only point inward: the domain knows nothing about Streamlit, yfinance or the file system.

**Patterns used**
- **Strategy:** every strategy (GEM, relative momentum, ...) implements one interface, so a new strategy needs no change to the backtest engine.
- **Ports & Adapters:** data access sits behind a `PriceProvider` interface; Yahoo Finance is just one adapter and can be swapped for another source.
- **Decorator:** `CachedPriceProvider` wraps any provider with a local CSV cache.
- **Dependency Injection:** `app.py` is the only place where concrete classes are wired together (composition root).
- **Functional core, imperative shell:** domain functions take data in and return results, with no side effects.
- **ViewModel:** turns a `BacktestResult` into display-ready tables and series; views only render them. (Streamlit re-runs the script on every interaction and has no two-way data binding, so classic MVVM doesn't fit directly, but the View/ViewModel separation is kept.)

## Project Structure

```
gem-strategy-backtester/
├── app.py                           # Streamlit entry point (composition root)
├── pyproject.toml                   # Dependencies and tool configuration
├── src/gem_backtester/
│   ├── domain/                      # Pure logic: no I/O, no Streamlit, no yfinance
│   │   ├── models.py                # Frozen dataclasses: configs, Allocation, BacktestResult
│   │   ├── momentum.py              # Momentum calculations (e.g. 12-1 month)
│   │   ├── filters.py               # Market-trend filter, liquidity filter
│   │   ├── strategies/
│   │   │   ├── base.py              # Strategy interface: select(prices, date) -> Allocation
│   │   │   ├── gem.py               # Classic GEM (relative + absolute momentum)
│   │   │   └── relative_momentum.py # Custom top-N strategy with holding buffer
│   │   ├── portfolio.py             # Rebalancing and transaction costs
│   │   ├── engine.py                # Backtest loop: strategy + prices -> equity curve
│   │   └── metrics.py               # CAGR, volatility, Sharpe, max drawdown
│   ├── application/
│   │   ├── ports.py                 # PriceProvider and PriceCache interfaces
│   │   └── services.py              # RunBacktest use case (load -> engine -> metrics)
│   ├── infrastructure/
│   │   ├── yfinance_provider.py     # PriceProvider adapter for Yahoo Finance
│   │   ├── csv_cache.py             # PriceCache adapter
│   │   └── cached_provider.py       # Decorator: provider + cache
│   └── presentation/
│       ├── view_models.py           # BacktestResult -> display-ready data (no Streamlit)
│       ├── theme.py                 # Colors and styling constants
│       ├── components/              # Sidebar, charts, tables
│       └── pages/                   # Streamlit pages (rendering only)
└── tests/
    ├── unit/                        # Domain and view-model tests
    ├── integration/                 # Services with fake providers, adapter tests
    ├── fixtures/                    # Small hand-checked price datasets
    └── test_architecture.py         # Enforces the dependency rules
```

## Technologies

- **Python 3.11+:** core language
- **pandas & NumPy:** time-series processing and return calculations
- **yfinance:** historical market data (used only inside the infrastructure layer)
- **Streamlit:** interactive dashboard and dark-theme UI
- **Plotly:** interactive charts
- **pytest & pytest-cov:** test runner and coverage
- **Hypothesis:** property-based testing
- **ruff & mypy:** linting, formatting and static type checking
- **import-linter:** fails the build if a layer imports something it shouldn't

## Testing Strategy

- **Unit tests (domain):** pure functions tested with tiny hand-built price tables, covering momentum calculation, strategy selection, filters and metrics.
- **No look-ahead bias:** property-based tests check that a decision on date *t* never changes when prices after *t* change.
- **Golden tests:** GEM results on small fixtures are compared with hand-calculated numbers.
- **Integration tests:** the `RunBacktest` service runs against a fake `PriceProvider` (no network); adapters are tested against recorded responses.
- **ViewModel tests:** plain function tests, no Streamlit needed.
- **Architecture test:** import-linter checks that the domain never imports Streamlit, yfinance or outer layers.

## UI Theme

Designed with a low-fatigue, high-contrast dark theme optimized for quant dashboards:
- **Background:** Charcoal (`#0E1117`)
- **Panels & Cards:** Dark Slate (`#1E232A`)
- **Accent & Gains:** Emerald Green (`#00C853`)