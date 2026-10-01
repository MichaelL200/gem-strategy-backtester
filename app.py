"""Streamlit app: pick assets and a lookback; each month hold the best performer."""

import pandas as pd
import plotly.express as px
import streamlit as st

from gem_backtester import backtest
from gem_backtester.assets import ASSETS, CATEGORIES
from gem_backtester.data import load_prices

DEFAULT_ASSETS = {"S&P 500", "MSCI ACWI"}
GREEN = "#00C853"

st.set_page_config(page_title="Momentum Backtester", layout="wide")
st.markdown(
    "<style>section[data-testid='stSidebar']{width:440px !important;min-width:440px !important}"
    "</style>",
    unsafe_allow_html=True,
)
st.title("Momentum Backtester")

st.sidebar.markdown("### Assets")
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
st.sidebar.divider()
lookback = st.sidebar.slider("Lookback (months)", 1, 24, 12)
skip = st.sidebar.slider("Ignore last months", 0, 6, 0)

if len(names) < 2:
    st.info("Choose at least two assets.")
    st.stop()


@st.cache_data(ttl=12 * 3600)
def prices_for(tickers: tuple[str, ...]) -> pd.DataFrame:
    return load_prices(list(tickers))


try:
    prices = prices_for(tuple(ASSETS[n] for n in names))
    result = backtest.run(prices, lookback, skip)
except ValueError as error:
    st.error(str(error))
    st.stop()

label = {ticker: name for name, ticker in ASSETS.items()}
cols = st.columns(5)
cols[0].metric("CAGR", f"{result.cagr:.1%}")
cols[1].metric("Total return", f"{result.total_return:.1%}")
cols[2].metric("Volatility", f"{result.volatility:.1%}")
cols[3].metric("Sharpe", f"{result.sharpe:.2f}")
cols[4].metric("Max drawdown", f"{result.max_drawdown:.1%}")
st.caption(
    f"Latest pick: **{label[result.picks.iloc[-1]]}** (as of {result.picks.index[-1]:%Y-%m-%d})"
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
