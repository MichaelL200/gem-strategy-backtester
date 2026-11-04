"""Streamlit app: pick assets, a lookback and a rebalancing period; hold the best performer."""

import math
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.components.charts import (
    create_composition_chart,
    create_drawdown_chart,
    create_main_chart,
)
from app.components.sidebar import highlight, is_mobile, prices_for
import backtest
from assets import CATEGORIES, normalize_ticker, split_tickers
from data import CURRENCIES, load_prices
from periods import COMMON, CUSTOM, MODES, availability, duration_text, window_text

DEFAULT_ASSETS = {"MSCI World (DM)", "Gold", "Bonds 7-10Y", "Bonds 0-1Y"}
DEFAULT_LOOKBACK = 12
DEFAULT_SKIP = 1
DEFAULT_REBALANCE = 1
STRATEGIES = {  # option -> the strategies to run
    "Normal": ("Normal",),
    "Volatility-adjusted": ("Volatility-adjusted",),
    "Both": ("Normal", "Volatility-adjusted"),
}
GREEN = "#00C853"
PINK = "#FF1493"  # second strategy, when both are shown
ORANGE = "#FFA000"  # warnings about the settings
RED = "#FF4B4B"  # invalid settings

st.set_page_config(page_title="Momentum Backtester", layout="wide")
st.markdown(
    # wide sidebar on large screens only: on phones Streamlit shows it over the page
    "<style>@media (min-width:769px){"
    "section[data-testid='stSidebar']{width:440px !important;min-width:440px !important}}"
    # let the long "Period" value (e.g. "13 years 8 months") wrap instead of ending with "..."
    "[data-testid='stColumn']:first-child [data-testid='stMetricValue'],"
    "[data-testid='stColumn']:first-child [data-testid='stMetricValue'] *{white-space:normal !important;"
    "overflow:visible !important;text-overflow:clip !important;overflow-wrap:normal !important;"
    "word-break:normal !important;line-height:1.15 !important}"
    # main chart: about the rest of the window below the header, but never tiny or huge
    # (Streamlit also fixes the height of the two wrapper elements, so all three need it,
    # and the outer one has flex-basis 450px, which wins over height)
    ".stElementContainer.st-key-main_chart{flex:0 0 auto !important}"
    ".stElementContainer.st-key-main_chart,"
    ".stElementContainer.st-key-main_chart [data-testid='stFullScreenFrame'],"
    ".stElementContainer.st-key-main_chart [data-testid='stPlotlyChart']"
    "{height:clamp(560px,calc(100vh - 400px),900px) !important}"
    # phones and narrow windows: smaller margins and text, the metrics two per row (the first
    # one, Period or Strategy, on its own row), Select all / Clear side by side, a lower chart
    "@media (max-width:768px){"
    ".block-container{padding:3rem 1rem 2rem !important}"
    "h1{font-size:1.8rem !important}"
    "[data-testid='stMetricValue']{font-size:1.6rem !important}"
    "[class*='st-key-metrics'] [data-testid='stHorizontalBlock']"
    "{flex-wrap:wrap !important;gap:.5rem 0 !important}"
    "[class*='st-key-metrics'] [data-testid='stColumn']"
    "{flex:1 1 calc(50% - 1rem) !important;min-width:calc(50% - 1rem) !important}"
    "[class*='st-key-metrics'] [data-testid='stColumn']:first-child{flex-basis:100% !important}"
    ".st-key-select_clear [data-testid='stHorizontalBlock']{flex-wrap:nowrap !important}"
    ".st-key-select_clear [data-testid='stColumn']{min-width:0 !important}"
    ".stElementContainer.st-key-main_chart,"
    ".stElementContainer.st-key-main_chart [data-testid='stFullScreenFrame'],"
    ".stElementContainer.st-key-main_chart [data-testid='stPlotlyChart']"
    "{height:clamp(480px,70vh,640px) !important}}"
    "</style>",
    unsafe_allow_html=True,
)
st.title("Momentum Backtester")


mobile = is_mobile()
if mobile:  # the sidebar is closed on phones
    st.caption("Tap the arrow at the top left to change the settings.")
notices = st.container()  # warnings about the settings; filled further down


# ---- 1. Currency -----------------------------------------------------------
st.sidebar.markdown("### 1 · Currency")
st.sidebar.caption("The currency the backtest is calculated in; prices are converted daily.")
currency = st.sidebar.selectbox(
    "Currency", CURRENCIES, key="currency", label_visibility="collapsed"
)


def categories() -> dict[str, dict[str, str]]:
    """The built-in categories plus the tickers added by the user (name = ticker)."""
    custom = st.session_state.get("custom_tickers", [])
    return {**CATEGORIES, **({"Custom": {t: t for t in custom}} if custom else {})}


def all_assets() -> dict[str, str]:
    return {name: ticker for group in categories().values() for name, ticker in group.items()}


assets = all_assets()

# ---- 2. Benchmarks ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 2 · Benchmarks")
default_bench = ["MSCI World (DM)"] if "MSCI World (DM)" in assets else []
benchmarks = st.sidebar.multiselect(
    "Benchmarks",
    options=list(assets.keys()),
    default=default_bench,
    format_func=lambda n: n if n == assets[n] else f"{n} · {assets[n]}",
    label_visibility="collapsed",
)


# ---- 3. Assets -------------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 3 · Assets")

def select_assets(mode: str) -> None:
    for category, group in categories().items():
        if mode == "all":
            st.session_state[f"pills_{category}"] = list(group)
        elif mode == "default":
            st.session_state[f"pills_{category}"] = [n for n in group if n in DEFAULT_ASSETS]
        else:  # clear
            st.session_state[f"pills_{category}"] = []


def add_tickers() -> None:
    """Add the tickers typed or pasted by the user; each is downloaded now, so one without data is refused.

    The valid ones are added even if others in the same text are refused.
    """
    st.session_state.pop("ticker_error", None)
    text = st.session_state.new_ticker
    tokens = split_tickers(text) or [text]  # nothing found: let normalize_ticker explain
    known = {t: name for name, t in all_assets().items()}
    added: list[str] = []
    errors: list[str] = []
    for token in tokens:
        try:
            ticker = normalize_ticker(token)
            if ticker in known:
                raise ValueError(f"{ticker} is already in the list ({known[ticker]})")
            load_prices([ticker])
        except Exception as error:
            errors.append(str(error))
            continue
        known[ticker] = ticker
        added.append(ticker)
    if added:
        st.session_state.custom_tickers = [*st.session_state.get("custom_tickers", []), *added]
        st.session_state["pills_Custom"] = [*st.session_state.get("pills_Custom", []), *added]
    if len(tokens) == 1 and errors:
        st.session_state.ticker_error = f"Could not add the ticker: {errors[0]}"
    elif errors:
        st.session_state.ticker_error = (
            f"Could not add {len(errors)} of {len(tokens)} tickers: " + "; ".join(errors)
        )


with st.sidebar.container(key="select_clear"):
    cols = st.columns(3)
cols[0].button("All", on_click=select_assets, args=("all",), width="stretch")
cols[1].button("Default", on_click=select_assets, args=("default",), width="stretch")
cols[2].button("Clear", on_click=select_assets, args=("clear",), width="stretch")

names: list[str] = []
with st.sidebar.container(key="assets"):
    for category, group in categories().items():
        st.caption(category.upper())
        if f"pills_{category}" not in st.session_state:  # first run: the default assets
            st.session_state[f"pills_{category}"] = [n for n in group if n in DEFAULT_ASSETS]
        names += st.pills(
            category,
            list(group),
            selection_mode="multi",
            format_func=lambda n: n if n == assets[n] else f"{n} · {assets[n]}",
            key=f"pills_{category}",
            label_visibility="collapsed",
        )

with st.sidebar.container(key="add_ticker"):
    st.caption("ADD YOUR OWN TICKERS")
    with st.form("add_ticker_form", clear_on_submit=True, border=False):
        st.text_area(
            "Add your own tickers",
            key="new_ticker",
            placeholder="e.g. NVDA, AAPL, MSFT",
            height=100,
            label_visibility="collapsed",
        )
        st.form_submit_button("Add", on_click=add_tickers)
    st.caption(
        "Any Yahoo Finance symbols, e.g. ^GSPC, EURUSD=X, BTC-USD. Add many at once, "
        "separated by spaces, commas, semicolons, | or new lines."
    )
if "ticker_error" in st.session_state:  # shown once, right after the failed attempt
    notices.warning(st.session_state.pop("ticker_error"))
    highlight("add_ticker")

# Hold top N: the chosen N is remembered; it is cut down to the number of selected assets.
n_assets = len(names)
top_n = 1
if n_assets >= 2:
    st.session_state.top_n = min(st.session_state.get("saved_top_n", 1), n_assets)
    st.sidebar.slider(
        "Hold top N assets (equal weights)",
        1,
        n_assets,
        key="top_n",
        # .get: the widget key is dropped when the slider is hidden (fewer than 2 assets)
        on_change=lambda: st.session_state.update(
            saved_top_n=st.session_state.get("top_n", st.session_state.get("saved_top_n", 1))
        ),
    )
    top_n = st.session_state.top_n
    st.session_state.saved_top_n = top_n
    if top_n == n_assets:
        notices.warning(
            f"**N = {top_n}** is the number of selected assets: all are held in equal weights "
            "and the momentum ranking is ignored."
        )
        highlight("top_n")
else:
    notices.warning(
        "Choose at least one asset."
        if n_assets == 0
        else "Only one asset is selected: there is nothing to rank, so the strategy always holds "
        "it. Choose at least two assets to compare."
    )
    highlight("assets")

show_assets = st.sidebar.toggle(
    "Show assets on the chart",
    value=True,
    key="show_assets",
)

# ---- 4. Momentum -----------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 4 · Momentum")
st.sidebar.caption("How each asset's past performance is measured to rank it.")
strategy = st.sidebar.radio(
    "Momentum",
    list(STRATEGIES),
    index=list(STRATEGIES).index("Both"),
    label_visibility="collapsed",
    key="strategy",
    captions=[
        "The return over the window",
        "The return divided by the volatility over the window",
        "Compare both",
    ],
)
with st.sidebar.container(key="lookback_window"):
    lookback = st.slider("Look back (months)", 1, 24, DEFAULT_LOOKBACK)
    skip = st.slider("Ignore the most recent (months)", 0, 6, DEFAULT_SKIP)
if lookback > skip:
    st.sidebar.info(f"Window length: **{window_text(lookback, skip)}**")
else:
    st.sidebar.warning("The lookback must be longer than the ignored months.")
    highlight("lookback_window", RED)
with st.sidebar.container(key="outliers"):
    exclude_outliers = st.toggle(
        "Exclude top outliers",
        key="exclude_outliers",
        help="Skip an asset whose score is extremely high compared with the others "
        "(e.g. +1156% when the rest are around +400%), and pick the best of the rest.",
    )
    outlier_threshold = None
    if exclude_outliers:
        outlier_threshold = st.slider(
            "Outlier threshold (lower = stronger)",
            2.0,
            10.0,
            backtest.DEFAULT_OUTLIER_THRESHOLD,
            0.5,
            key="outlier_threshold",
        )
        st.caption(
            "An asset is skipped when its score is this many robust standard deviations above "
            "the median score of the ranked assets. 3.5 is the usual cut-off; 2-3 skips more "
            "assets, 5 or more only the most extreme."
        )
if exclude_outliers and n_assets < backtest.MIN_OUTLIER_ASSETS:
    notices.warning(
        f"Excluding outliers needs at least {backtest.MIN_OUTLIER_ASSETS} ranked assets: "
        "with fewer, nothing is excluded."
    )
    highlight("outliers")

# ---- 5. Rebalancing --------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 5 · Rebalancing")
st.sidebar.caption("How often the ranking is redone and the portfolio switches to the winner.")
rebalance = st.sidebar.slider("Rebalance every (months)", 1, 12, DEFAULT_REBALANCE)

# ---- 6. Backtest period ----------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 6 · Backtest period")
mode = st.sidebar.radio(
    "Period to backtest",
    MODES,
    index=MODES.index(COMMON),
    label_visibility="collapsed",
    captions=[
        "Everything available; assets join once they have enough history",
        "Only when every selected asset can be ranked",
        "Pick the dates yourself",
    ],
)

period_box = st.sidebar.container()  # the dates and the data table of section 6 go here

if not names:
    st.stop()

try:
    asset_tickers = [assets[n] for n in names]
    bench_tickers = [assets[b] for b in benchmarks]

    # Extract unique tickers while maintaining predictable order
    all_tickers_list = []
    for t in asset_tickers + bench_tickers:
        if t not in all_tickers_list:
            all_tickers_list.append(t)

    prices = prices_for(tuple(all_tickers_list), currency)
except ValueError as error:
    st.error(str(error))
    st.stop()

label = {ticker: name for name, ticker in assets.items()}
if prices.attrs.get("unknown_currency"):
    notices.warning(
        f"The currency of {', '.join(prices.attrs['unknown_currency'])} could not be found, "
        "so its prices are taken as USD."
    )
    highlight("assets")

asset_prices = prices[asset_tickers]
avail = availability(asset_prices, lookback, skip) if lookback > skip else None

start = end = None
if mode == CUSTOM:
    first, last = asset_prices.index[0], asset_prices.index[-1]
    ranked = avail["Ranked from"] if avail is not None else None
    common_from = ranked.max() if ranked is not None and ranked.notna().all() else first
    picked = period_box.date_input(
        "From – to",
        value=(min(common_from, last).date(), last.date()),
        min_value=first.date(),
        max_value=last.date(),
        format="YYYY-MM-DD",
    )
    if len(picked) != 2:
        period_box.info("Pick the end date.")
        st.stop()
    start, end = (pd.Timestamp(d) for d in picked)

if avail is not None:
    with period_box.expander("Data available per asset"):
        table = avail.rename(index=label).apply(lambda c: c.dt.strftime("%Y-%m-%d"))
        st.dataframe(table.fillna("not enough history"), width="stretch")
        st.caption("'Ranked from' = first month-end with a full lookback window.")

results = {}
try:
    for name in STRATEGIES[strategy]:
        results[name] = backtest.run(
            asset_prices, lookback, skip, start=start, end=end, common=mode == COMMON,
            rebalance=rebalance, top_n=top_n, volatility_adjusted=name == "Volatility-adjusted",
            outlier_threshold=outlier_threshold,
        )
except ValueError as error:
    st.error(str(error))
    st.stop()

result = next(iter(results.values()))  # the period is the same for both
both = len(results) == 2
duration = duration_text(result.start, result.end)


def metrics(index: int, first_label: str, first_value: str, r: backtest.Result) -> None:
    with st.container(key=f"metrics_{index}"):
        cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
        cols[0].metric(first_label, first_value)
        cols[1].metric(
            "CAGR",
            f"{r.cagr:.1%}",
            help="The yearly return your investment would have earned if it had grown at a steady compounded rate over the whole period.",
        )
        cols[2].metric(
            "Total return",
            f"{r.total_return:.1%}",
            help="How much the investment gained or lost from start to finish, including the effect of compounding.",
        )
        cols[3].metric(
            "Volatility",
            f"{r.volatility:.1%}",
            help="How much daily returns varied. Higher values mean a bumpier ride; it is annualized using 252 trading days.",
        )
        cols[4].metric(
            "Sharpe",
            f"{r.sharpe:.2f}" if math.isfinite(r.sharpe) else "n/a",
            help="Return earned for each unit of overall price variation. It is the average daily return, annualized, divided by annualized volatility.",
        )
        cols[5].metric(
            "Sortino",
            f"{r.sortino:.2f}" if math.isfinite(r.sortino) else "n/a",
            help="Return earned for each unit of downside risk. It uses only negative daily returns when measuring risk, with both return and risk annualized.",
        )
        cols[6].metric(
            "Calmar",
            f"{r.calmar:.2f}" if math.isfinite(r.calmar) else "n/a",
            help="Annualized return compared with the worst peak-to-trough loss. Higher values mean more return relative to the biggest setback.",
        )
        cols[7].metric(
            "Max drawdown",
            f"{r.max_drawdown:.1%}",
            help="The largest percentage loss from an earlier portfolio peak before recovering or reaching the end of the period.",
        )


if both:
    for i, (name, r) in enumerate(results.items()):
        metrics(i, "Strategy", name, r)
else:
    metrics(0, "Period", duration, result)

picks = "; ".join(
    f"{', '.join(label[t] for t in r.picks.iloc[-1])}" + (f" ({name})" if both else "")
    for name, r in results.items()
)
in_currency = f"Currency: **{currency}** · " if currency != "USD" else ""
st.caption(
    f"Backtest: **{result.start:%Y-%m-%d} → {result.end:%Y-%m-%d}** ({duration}) · {in_currency}"
    f"Latest pick{'s' if both or len(result.picks.iloc[-1]) > 1 else ''}: **{picks}** "
    f"(as of {result.picks.index[-1]:%Y-%m-%d})"
)
if outlier_threshold is not None and n_assets >= backtest.MIN_OUTLIER_ASSETS:
    cut = "; ".join(
        ", ".join(label[t] for t in r.excluded.iloc[-1]) + (f" ({name})" if both else "")
        for name, r in results.items()
        if len(r.excluded.iloc[-1])
    )
    st.caption(f"Excluded as outliers at the latest rebalance: **{cut or 'none'}**")
if mode == CUSTOM and result.start > start + pd.Timedelta(days=31):
    st.caption(
        f"Trading starts at the first month-end with enough history, {result.start:%Y-%m-%d}."
    )
st.caption("↓ Scroll down for the drawdown and portfolio composition charts.")

line_names = {name: f"Strategy ({name})" if both else "Strategy" for name in results}
line_colors = dict(zip(results, (GREEN, PINK)))
compare = result.assets.rename(columns=label)

if benchmarks:
    bench_prices = prices[bench_tickers].loc[result.start:result.end].ffill()
    if not bench_prices.empty:
        # Rebase to start at 1 based on the first available valid price
        bench_equity = bench_prices / bench_prices.bfill().iloc[0]
        bench_equity = bench_equity.rename(columns=label)
        for b in benchmarks:
            if b not in compare.columns:
                compare[b] = bench_equity[b]

for name, r in results.items():
    compare[line_names[name]] = r.equity

# Keep the stable palette based on insertion order while sorting the legend by returns.
color_order = list(compare.columns)
compare = compare[compare.iloc[-1].sort_values(ascending=False).index]

fig, colors = create_main_chart(
    compare,
    line_names,
    line_colors,
    bool(benchmarks),
    mobile,
    color_order,
)
if not show_assets:
    # Hide after building the chart: the colors were assigned with the assets included, so the
    # composition charts still find them and nothing changes color when the toggle flips.
    hidden = set(compare.columns) - set(benchmarks) - set(line_names.values())
    fig.data = tuple(trace for trace in fig.data if trace.name not in hidden)
st.plotly_chart(fig, width="stretch", key="main_chart")

drawdown_fig = create_drawdown_chart(results, line_colors, mobile, both)
if benchmarks:
    # The chart may plot fractions (-0.25) or percent (-25): copy whatever scale it already uses
    # by comparing its first line with the drawdown of the first strategy.
    first_equity = next(iter(results.values())).equity
    first_drawdown = (first_equity / first_equity.cummax() - 1).min()
    plotted_min = min(drawdown_fig.data[0].y)
    scale = 100 if first_drawdown and abs(plotted_min / first_drawdown) > 10 else 1
    for b in benchmarks:
        series = compare[b].dropna()
        drawdown = (series / series.cummax() - 1) * scale
        drawdown_fig.add_scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode="lines",
            name=b,
            line={"color": colors.get(b), "width": 1.5},  # same color as in the main chart
            showlegend=True,
        )
    drawdown_fig.update_layout(showlegend=True)
    if mobile:
        drawdown_fig.update_layout(legend={"orientation": "h"})
st.plotly_chart(drawdown_fig, width="stretch")

for name, r in results.items():
    st.plotly_chart(
        create_composition_chart(r, label, colors, mobile, name, both),
        width="stretch",
        key=f"composition_{name}",
    )
