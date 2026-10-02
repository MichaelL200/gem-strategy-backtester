"""Streamlit app: pick assets, a lookback and a rebalancing period; hold the best performer."""

import pandas as pd
import plotly.express as px
import streamlit as st

from gem_backtester import backtest
from gem_backtester.assets import ASSETS, CATEGORIES
from gem_backtester.data import load_prices
from gem_backtester.periods import ALL, COMMON, CUSTOM, MODES, availability, duration_text, window_text

DEFAULT_ASSETS = {"MSCI World", "Gold", "Bonds 7-10Y", "Bonds 0-1Y"}
DEFAULT_LOOKBACK = 12
DEFAULT_SKIP = 1
DEFAULT_REBALANCE = 1
GREEN = "#00C853"

st.set_page_config(page_title="Momentum Backtester", layout="wide")
st.markdown(
    "<style>section[data-testid='stSidebar']{width:440px !important;min-width:440px !important}"
    "</style>",
    unsafe_allow_html=True,
)
st.title("Momentum Backtester")

@st.cache_data(ttl=12 * 3600)
def prices_for(tickers: tuple[str, ...]) -> pd.DataFrame:
    return load_prices(list(tickers))


# ---- 1. Assets -------------------------------------------------------------
st.sidebar.markdown("### 1 · Assets")
names: list[str] = []
for category, group in CATEGORIES.items():
    st.sidebar.caption(category.upper())
    names += st.sidebar.pills(
        category,
        list(group),
        selection_mode="multi",
        default=[n for n in group if n in DEFAULT_ASSETS],
        format_func=lambda n: f"{n} · {ASSETS[n]}",
        key=f"pills_{category}",
        label_visibility="collapsed",
    )

# ---- 2. Lookback window ----------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 2 · Lookback window")
st.sidebar.caption("How far back each asset's past performance is measured to rank it.")
lookback = st.sidebar.slider("Look back (months)", 1, 24, DEFAULT_LOOKBACK)
skip = st.sidebar.slider("Ignore the most recent (months)", 0, 6, DEFAULT_SKIP)
if lookback > skip:
    until = f"{skip} month{'s' if skip != 1 else ''} ago" if skip else "now"
    st.sidebar.info(
        f"Window length: **{window_text(lookback, skip)}**  \n"
        f"Performance from {lookback} months ago to {until}."
    )
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
    label_visibility="collapsed",
    captions=[
        "Everything available; assets join once they have enough history",
        "Only when every selected asset can be ranked",
        "Pick the dates yourself",
    ],
)

if len(names) < 2:
    st.info("Choose at least two assets.")
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
        prices, lookback, skip, start=start, end=end, common=mode == COMMON, rebalance=rebalance
    )
except ValueError as error:
    st.error(str(error))
    st.stop()

duration = duration_text(result.start, result.end)
cols = st.columns(6)
cols[0].metric("Period", duration, help=f"{result.start:%Y-%m-%d} → {result.end:%Y-%m-%d}")
cols[1].metric("CAGR", f"{result.cagr:.1%}")
cols[2].metric("Total return", f"{result.total_return:.1%}")
cols[3].metric("Volatility", f"{result.volatility:.1%}")
cols[4].metric("Sharpe", f"{result.sharpe:.2f}")
cols[5].metric("Max drawdown", f"{result.max_drawdown:.1%}")
st.caption(
    f"Backtest: **{result.start:%Y-%m-%d} → {result.end:%Y-%m-%d}** ({duration}) · "
    f"Latest pick: **{label[result.picks.iloc[-1]]}** (as of {result.picks.index[-1]:%Y-%m-%d})"
)
if mode == CUSTOM and result.start > start + pd.Timedelta(days=31):
    st.caption(
        f"Trading starts at the first month-end with enough history, {result.start:%Y-%m-%d}."
    )

compare = result.assets.rename(columns=label).assign(Strategy=result.equity)
fig = px.line(compare, log_y=True, title="Strategy vs. assets held alone (start = 1)")
fig.update_traces(line_width=1.2)
fig.update_traces(line={"width": 3.5, "color": GREEN}, selector={"name": "Strategy"})
fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="")
st.plotly_chart(fig, width="stretch")
st.plotly_chart(px.area(result.drawdown * 100, title="Strategy drawdown (%)"), width="stretch")
st.plotly_chart(
    px.scatter(
        result.picks.map(label).rename("Asset"), title="Picks", labels={"value": "", "index": ""}
    ),
    width="stretch",
)
