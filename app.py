"""Streamlit app: pick assets, a lookback and a rebalancing period; hold the best performer."""

import pandas as pd
import plotly.express as px
import streamlit as st

from gem_backtester import backtest
from gem_backtester.assets import ASSETS, CATEGORIES
from gem_backtester.data import load_prices
from gem_backtester.periods import ALL, COMMON, CUSTOM, MODES, availability, duration_text, window_text

DEFAULT_ASSETS = {"MSCI World (DM)", "Gold", "Bonds 7-10Y", "Bonds 0-1Y"}
DEFAULT_LOOKBACK = 12
DEFAULT_SKIP = 1
DEFAULT_REBALANCE = 1
GREEN = "#00C853"

st.set_page_config(page_title="Momentum Backtester", layout="wide")
st.markdown(
    "<style>section[data-testid='stSidebar']{width:440px !important;min-width:440px !important}"
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
    "</style>",
    unsafe_allow_html=True,
)
st.title("Momentum Backtester")
notices = st.container()  # warnings about the settings; filled further down


def highlight(key: str) -> None:
    """Orange frame around the setting (a widget or container key) a warning is about."""
    st.markdown(
        f"<style>.st-key-{key}{{outline:2px solid #FFA000;outline-offset:6px;border-radius:6px}}</style>",
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=12 * 3600)
def prices_for(tickers: tuple[str, ...]) -> pd.DataFrame:
    return load_prices(list(tickers))


# ---- 1. Assets -------------------------------------------------------------
st.sidebar.markdown("### 1 · Assets")


def select_assets(select: bool) -> None:
    for category, group in CATEGORIES.items():
        st.session_state[f"pills_{category}"] = list(group) if select else []


select_col, clear_col = st.sidebar.columns(2)
select_col.button("Select all", on_click=select_assets, args=(True,), width="stretch")
clear_col.button("Clear", on_click=select_assets, args=(False,), width="stretch")
names: list[str] = []
with st.sidebar.container(key="assets"):
    for category, group in CATEGORIES.items():
        st.caption(category.upper())
        if f"pills_{category}" not in st.session_state:  # first run: the default assets
            st.session_state[f"pills_{category}"] = [n for n in group if n in DEFAULT_ASSETS]
        names += st.pills(
            category,
            list(group),
            selection_mode="multi",
            format_func=lambda n: f"{n} · {ASSETS[n]}",
            key=f"pills_{category}",
            label_visibility="collapsed",
        )

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
        on_change=lambda: st.session_state.update(saved_top_n=st.session_state.top_n),
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

# ---- 2. Lookback window ----------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 2 · Lookback window")
st.sidebar.caption("How far back each asset's past performance is measured to rank it.")
lookback = st.sidebar.slider("Look back (months)", 1, 24, DEFAULT_LOOKBACK)
skip = st.sidebar.slider("Ignore the most recent (months)", 0, 6, DEFAULT_SKIP)
if lookback > skip:
    st.sidebar.info(f"Window length: **{window_text(lookback, skip)}**")
else:
    st.sidebar.warning("The lookback must be longer than the ignored months.")

# ---- 3. Rebalancing --------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 3 · Rebalancing")
st.sidebar.caption("How often the ranking is redone and the portfolio switches to the winner.")
rebalance = st.sidebar.slider("Rebalance every (months)", 1, 12, DEFAULT_REBALANCE)

# ---- 4. Backtest period ----------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 4 · Backtest period")
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

if not names:
    st.stop()

try:
    prices = prices_for(tuple(ASSETS[n] for n in names))
except ValueError as error:
    st.error(str(error))
    st.stop()

label = {ticker: name for name, ticker in ASSETS.items()}
avail = availability(prices, lookback, skip) if lookback > skip else None
start = end = None
if mode == CUSTOM:
    first, last = prices.index[0], prices.index[-1]
    ranked = avail["Ranked from"] if avail is not None else None
    common_from = ranked.max() if ranked is not None and ranked.notna().all() else first
    picked = st.sidebar.date_input(
        "From – to",
        value=(min(common_from, last).date(), last.date()),
        min_value=first.date(),
        max_value=last.date(),
        format="YYYY-MM-DD",
    )
    if len(picked) != 2:
        st.sidebar.info("Pick the end date.")
        st.stop()
    start, end = (pd.Timestamp(d) for d in picked)

if avail is not None:
    with st.sidebar.expander("Data available per asset"):
        table = avail.rename(index=label).apply(lambda c: c.dt.strftime("%Y-%m-%d"))
        st.dataframe(table.fillna("not enough history"), width="stretch")
        st.caption("'Ranked from' = first month-end with a full lookback window.")

try:
    result = backtest.run(
        prices, lookback, skip, start=start, end=end, common=mode == COMMON,
        rebalance=rebalance, top_n=top_n,
    )
except ValueError as error:
    st.error(str(error))
    st.stop()

duration = duration_text(result.start, result.end)
cols = st.columns([2, 1, 1, 1, 1, 1])
cols[0].metric("Period", duration)
cols[1].metric("CAGR", f"{result.cagr:.1%}")
cols[2].metric("Total return", f"{result.total_return:.1%}")
cols[3].metric("Volatility", f"{result.volatility:.1%}")
cols[4].metric("Sharpe", f"{result.sharpe:.2f}")
cols[5].metric("Max drawdown", f"{result.max_drawdown:.1%}")
last_picks = ", ".join(label[t] for t in result.picks.iloc[-1])
st.caption(
    f"Backtest: **{result.start:%Y-%m-%d} → {result.end:%Y-%m-%d}** ({duration}) · "
    f"Latest pick{'s' if len(result.picks.iloc[-1]) > 1 else ''}: **{last_picks}** "
    f"(as of {result.picks.index[-1]:%Y-%m-%d})"
)
if mode == CUSTOM and result.start > start + pd.Timedelta(days=31):
    st.caption(
        f"Trading starts at the first month-end with enough history, {result.start:%Y-%m-%d}."
    )

st.caption("↓ Scroll down for the drawdown and portfolio composition charts.")
compare = result.assets.rename(columns=label).assign(Strategy=result.equity)
colors = {name: px.colors.qualitative.Plotly[i % 10] for i, name in enumerate(compare.columns)}
fig = px.line(
    compare, log_y=True, title="Strategy vs. assets held alone (start = 1)", color_discrete_map=colors
)
fig.update_traces(line_width=1.2)
fig.update_traces(line={"width": 3.5, "color": GREEN}, legendrank=1, selector={"name": "Strategy"})
fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="", margin={"t": 60})
st.plotly_chart(fig, width="stretch", key="main_chart")
st.plotly_chart(px.area(result.drawdown * 100, title="Strategy drawdown (%)"), width="stretch")
fig = px.area(
    result.composition.rename(columns=label) * 100,
    groupnorm="percent",
    title="Portfolio composition (%)",
    color_discrete_map=colors,
)
fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="", yaxis_ticksuffix="%")
st.plotly_chart(fig, width="stretch")
