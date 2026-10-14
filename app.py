"""Streamlit app: pick assets, a lookback and a rebalancing period; hold the best performer."""

import pandas as pd
import plotly.express as px
import streamlit as st

from gem_backtester import backtest
from gem_backtester.assets import CATEGORIES, normalize_ticker, split_tickers
from gem_backtester.data import CURRENCIES, load_prices
from gem_backtester.periods import ALL, COMMON, CUSTOM, MODES, availability, duration_text, window_text

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


def highlight(key: str, color: str = ORANGE) -> None:
    """Frame (orange by default) around the setting (a widget or container key) a warning is about."""
    st.markdown(
        f"<style>.st-key-{key}{{outline:2px solid {color};outline-offset:6px;border-radius:6px}}</style>",
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=12 * 3600)
def prices_for(tickers: tuple[str, ...], currency: str) -> pd.DataFrame:
    return load_prices(list(tickers), currency)


# ---- 1. Assets -------------------------------------------------------------
st.sidebar.markdown("### 1 · Assets")


def categories() -> dict[str, dict[str, str]]:
    """The built-in categories plus the tickers added by the user (name = ticker)."""
    custom = st.session_state.get("custom_tickers", [])
    return {**CATEGORIES, **({"Custom": {t: t for t in custom}} if custom else {})}


def all_assets() -> dict[str, str]:
    return {name: ticker for group in categories().values() for name, ticker in group.items()}


def select_assets(select: bool) -> None:
    for category, group in categories().items():
        st.session_state[f"pills_{category}"] = list(group) if select else []


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


select_col, clear_col = st.sidebar.columns(2)
select_col.button("Select all", on_click=select_assets, args=(True,), width="stretch")
clear_col.button("Clear", on_click=select_assets, args=(False,), width="stretch")

assets = all_assets()
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

# ---- 2. Momentum -----------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 2 · Momentum")
st.sidebar.caption("How each asset's past performance is measured to rank it.")
strategy = st.sidebar.radio(
    "Momentum",
    list(STRATEGIES),
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

period_box = st.sidebar.container()  # the dates and the data table of section 4 go here

# ---- 5. Currency -----------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("### 5 · Currency")
st.sidebar.caption("The currency the backtest is calculated in; the USD prices are converted daily.")
currency = st.sidebar.selectbox(
    "Currency", CURRENCIES, key="currency", label_visibility="collapsed"
)

if not names:
    st.stop()

try:
    prices = prices_for(tuple(assets[n] for n in names), currency)
except ValueError as error:
    st.error(str(error))
    st.stop()

label = {ticker: name for name, ticker in assets.items()}
avail = availability(prices, lookback, skip) if lookback > skip else None

start = end = None
if mode == CUSTOM:
    first, last = prices.index[0], prices.index[-1]
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
            prices, lookback, skip, start=start, end=end, common=mode == COMMON,
            rebalance=rebalance, top_n=top_n, volatility_adjusted=name == "Volatility-adjusted",
        )
except ValueError as error:
    st.error(str(error))
    st.stop()

result = next(iter(results.values()))  # the period is the same for both
both = len(results) == 2
duration = duration_text(result.start, result.end)


def metrics(first_label: str, first_value: str, r: backtest.Result) -> None:
    cols = st.columns([2, 1, 1, 1, 1, 1])
    cols[0].metric(first_label, first_value)
    cols[1].metric("CAGR", f"{r.cagr:.1%}")
    cols[2].metric("Total return", f"{r.total_return:.1%}")
    cols[3].metric("Volatility", f"{r.volatility:.1%}")
    cols[4].metric("Sharpe", f"{r.sharpe:.2f}")
    cols[5].metric("Max drawdown", f"{r.max_drawdown:.1%}")


if both:
    for name, r in results.items():
        metrics("Strategy", name, r)
else:
    metrics("Period", duration, result)

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
if mode == CUSTOM and result.start > start + pd.Timedelta(days=31):
    st.caption(
        f"Trading starts at the first month-end with enough history, {result.start:%Y-%m-%d}."
    )
st.caption("↓ Scroll down for the drawdown and portfolio composition charts.")

line_names = {name: f"Strategy ({name})" if both else "Strategy" for name in results}
line_colors = dict(zip(results, (GREEN, PINK)))
compare = result.assets.rename(columns=label)
for name, r in results.items():
    compare[line_names[name]] = r.equity
colors = {name: px.colors.qualitative.Plotly[i % 10] for i, name in enumerate(compare.columns)}
fig = px.line(
    compare, log_y=True, title="Strategy vs. assets held alone (start = 1)", color_discrete_map=colors
)
fig.update_traces(line_width=1.2)
for name in results:
    fig.update_traces(
        line={"width": 3.5, "color": line_colors[name]},
        legendrank=1,
        selector={"name": line_names[name]},
    )
fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="", margin={"t": 60})
st.plotly_chart(fig, width="stretch", key="main_chart")

if both:  # overlapping lines: areas would be stacked
    fig = px.line(
        pd.DataFrame({name: r.drawdown * 100 for name, r in results.items()}),
        title="Strategy drawdown (%)",
        color_discrete_map=line_colors,
    )
    fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="")
    st.plotly_chart(fig, width="stretch")
else:
    st.plotly_chart(px.area(result.drawdown * 100, title="Strategy drawdown (%)"), width="stretch")

for name, r in results.items():
    fig = px.area(
        r.composition.rename(columns=label) * 100,
        groupnorm="percent",
        title="Portfolio composition (%)" + (f" · {name}" if both else ""),
        color_discrete_map=colors,
    )
    fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="", yaxis_ticksuffix="%")
    st.plotly_chart(fig, width="stretch", key=f"composition_{name}")
