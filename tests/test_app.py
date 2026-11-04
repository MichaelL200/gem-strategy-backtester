import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import data
from assets import ASSETS, CATEGORIES

APP = str(Path(__file__).parent.parent / "app.py")


def fake_app(monkeypatch):
    index = pd.bdate_range("2015-01-01", "2024-12-31")
    rng = np.random.default_rng(0)

    def fake_load(ticker):
        if ticker == "NOPE":
            raise ValueError("No price data for NOPE")
        if ticker == "SPIKE":  # grows 1% a day: far above the others
            steps = np.arange(len(index))
            wiggle = 1 + 0.001 * np.where(steps % 2, 1, -1)
            return pd.Series(100 * 1.01**steps * wiggle, index=index)
        return pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(index))), index=index)

    monkeypatch.setattr(data, "_load", fake_load)
    monkeypatch.setattr(data, "_quote_currency", lambda t: None if t == "MYSTERY" else "USD")
    return AppTest.from_file(APP, default_timeout=60).run()


@pytest.fixture
def app(monkeypatch):
    return fake_app(monkeypatch)


ROW = 8  # metrics per row: the first one (Period or Strategy) and seven statistics


def rows(app) -> int:
    """How many rows of metrics are shown (one per strategy)."""
    return len(app.metric) // ROW


def selected(app) -> dict[str, list[str]]:
    return {g.key.removeprefix("pills_"): g.value for g in app.sidebar.button_group}


def test_select_all_and_clear(app):
    app.sidebar.button[0].click().run()  # All
    assert not app.exception
    assert selected(app) == {category: list(group) for category, group in CATEGORIES.items()}
    assert app.slider(key="top_n").max == len(ASSETS)

    app.sidebar.button[2].click().run()  # Clear
    assert not app.exception
    assert all(not names for names in selected(app).values())
    assert [w.value for w in app.warning] == ["Choose at least one asset."]
    assert "st-key-assets" in " ".join(m.value for m in app.markdown)


def test_select_all_keeps_chosen_n(app):
    app.slider(key="top_n").set_value(3).run()
    app.sidebar.button[0].click().run()
    assert app.slider(key="top_n").value == 3


def test_default_assets_are_selected_on_first_run(app):
    assert [n for names in selected(app).values() for n in names] == [
        "MSCI World (DM)", "Gold", "Bonds 7-10Y", "Bonds 0-1Y"
    ]


def test_warning_when_n_equals_number_of_assets(app):
    assert not app.warning
    app.slider(key="top_n").set_value(4).run()
    assert len(app.warning) == 1
    assert app.warning[0].value.startswith("**N = 4**")
    assert "st-key-top_n" in " ".join(m.value for m in app.markdown)


def test_window_info_has_only_the_length(app):
    assert [i.value for i in app.info] == ["Window length: **11 months**"]


def test_single_asset_shows_a_warning_and_the_charts(app):
    app.sidebar.button[2].click().run()  # Clear
    app.session_state["pills_Equities"] = ["S&P 500"]
    app.run()
    assert not app.exception
    assert len(app.warning) == 1
    assert app.warning[0].value.startswith("Only one asset is selected")
    assert "st-key-assets" in " ".join(m.value for m in app.markdown)
    assert not [s for s in app.slider if s.key == "top_n"]  # nothing to choose between
    assert rows(app) == 2  # both strategies
    assert len(app.get("plotly_chart")) == 4  # main, drawdown and one composition per strategy
    assert "S&P 500" in " ".join(c.value for c in app.caption if "Latest pick" in c.value)


def add_ticker(app, text):
    app.text_area(key="new_ticker").set_value(text)
    app.sidebar.button[3].click().run()  # the form's "Add" button (after All, Default and Clear)


def test_custom_ticker_is_added_and_selected(app):
    add_ticker(app, " nvda ")
    assert not app.exception
    assert not app.warning
    assert selected(app)["Custom"] == ["NVDA"]
    assert rows(app) == 2  # the backtest runs with the new asset

    app.sidebar.button[2].click().run()  # Clear
    assert selected(app)["Custom"] == []
    app.sidebar.button[0].click().run()  # All
    assert selected(app)["Custom"] == ["NVDA"]


def test_many_custom_tickers_are_added_at_once(app):
    add_ticker(app, "nvda, aapl;msft\nTSLA | ^GSPC  nvda")
    assert not app.exception
    assert not app.warning
    assert selected(app)["Custom"] == ["NVDA", "AAPL", "MSFT", "TSLA", "^GSPC"]
    assert rows(app) == 2


def test_good_tickers_are_kept_when_others_are_refused(app):
    add_ticker(app, "NVDA, NOPE; spy a/b, AAPL")
    assert not app.exception
    assert selected(app)["Custom"] == ["NVDA", "AAPL"]
    assert [w.value for w in app.warning] == [
        "Could not add 3 of 5 tickers: No price data for NOPE; "
        "SPY is already in the list (S&P 500); 'a/b' is not a valid ticker"
    ]
    assert "st-key-add_ticker" in " ".join(m.value for m in app.markdown)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("NOPE", "No price data for NOPE"),  # nothing to download
        ("spy", "SPY is already in the list (S&P 500)"),
        ("a/b", "'a/b' is not a valid ticker"),
        ("", "'' is not a valid ticker"),
    ],
)
def test_bad_custom_ticker_is_refused_with_a_warning(app, text, message):
    add_ticker(app, text)
    assert not app.exception
    assert [w.value for w in app.warning if w.value.startswith("Could not")] == [
        f"Could not add the ticker: {message}"
    ]
    assert "st-key-add_ticker" in " ".join(m.value for m in app.markdown)
    assert "Custom" not in selected(app)

    app.run()  # the warning is shown once
    assert not [w for w in app.warning if w.value.startswith("Could not")]


def test_strategy_choice_normal_volatility_adjusted_or_both(app):
    assert app.sidebar.radio(key="strategy").value == "Both"  # the default
    assert rows(app) == 2

    app.sidebar.radio(key="strategy").set_value("Normal").run()
    assert not app.exception
    assert rows(app) == 1

    app.sidebar.radio(key="strategy").set_value("Volatility-adjusted").run()
    assert not app.exception
    assert rows(app) == 1

    app.sidebar.radio(key="strategy").set_value("Both").run()
    assert not app.exception
    assert [m.value for m in app.metric if m.label == "Strategy"] == ["Normal", "Volatility-adjusted"]
    assert rows(app) == 2
    assert len(app.get("plotly_chart")) == 4  # main, drawdown and one composition per strategy
    assert "(Normal)" in " ".join(c.value for c in app.caption)


def test_currency_choice(app):
    assert app.selectbox(key="currency").value == "USD"
    assert "Currency:" not in " ".join(c.value for c in app.caption)

    app.selectbox(key="currency").set_value("EUR").run()
    assert not app.exception
    assert rows(app) == 2
    assert "Currency: **EUR**" in " ".join(c.value for c in app.caption)


def test_ticker_without_a_known_currency_gets_a_warning_but_is_added(app):
    add_ticker(app, "mystery")
    assert not app.exception
    assert selected(app)["Custom"] == ["MYSTERY"]
    assert [w.value for w in app.warning] == [
        "The currency of MYSTERY could not be found, so its prices are taken as USD."
    ]
    assert "st-key-assets" in " ".join(m.value for m in app.markdown)


PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"


def legends(app) -> list[str | None]:
    figures = [json.loads(chart.proto.spec) for chart in app.get("plotly_chart")]
    return [figure["layout"].get("legend", {}).get("orientation") for figure in figures]


def test_desktop_keeps_the_legend_on_the_right_and_has_no_hint(app):
    assert legends(app) == [None] * 4  # main, drawdown and two compositions
    assert not [c for c in app.caption if "arrow at the top left" in c.value]


def test_phone_gets_a_hint_and_the_legends_under_the_charts(monkeypatch):
    monkeypatch.setattr(st, "context", SimpleNamespace(headers={"User-Agent": PHONE}))
    phone = fake_app(monkeypatch)
    assert not phone.exception
    assert [c.value for c in phone.caption if "arrow at the top left" in c.value]
    phone.sidebar.radio(key="strategy").set_value("Normal").run()
    assert legends(phone) == ["h", None, "h"]  # the drawdown chart has no legend


def test_a_desktop_browser_is_not_a_phone(monkeypatch):
    monkeypatch.setattr(st, "context", SimpleNamespace(headers={"User-Agent": DESKTOP}))
    assert legends(fake_app(monkeypatch)) == [None] * 4


def test_phone_legends_with_both_strategies(monkeypatch):
    monkeypatch.setattr(st, "context", SimpleNamespace(headers={"User-Agent": PHONE}))
    phone = fake_app(monkeypatch)  # opens with both strategies
    assert not phone.exception
    assert legends(phone) == ["h", "h", "h", "h"]  # main, drawdown and two compositions


def test_layout_rules_for_small_screens(app):
    css = " ".join(m.value for m in app.markdown if m.value.startswith("<style>"))
    assert "@media (min-width:769px){section[data-testid='stSidebar']" in css  # wide only
    assert "@media (max-width:768px)" in css
    assert "st-key-metrics" in css and "st-key-select_clear" in css


def test_cash_alone_runs_with_a_warning_and_no_sharpe(app):
    app.sidebar.button[2].click().run()  # Clear
    app.session_state["pills_Cash"] = ["Cash (USD)"]
    app.run()
    assert not app.exception
    assert [m.value for m in app.metric if m.label == "Sharpe"] == ["n/a"] * 2  # no volatility
    assert len(app.warning) == 1
    assert app.warning[0].value.startswith("Only one asset is selected")
    assert rows(app) == 2


# ---- excluding top outliers --------------------------------------------------


def test_outliers_are_not_excluded_by_default(app):
    assert app.sidebar.toggle(key="exclude_outliers").value is False
    assert not [s for s in app.slider if s.key == "outlier_threshold"]
    assert "Excluded as outliers" not in " ".join(c.value for c in app.caption)


def test_the_top_outlier_is_excluded_and_named(app):
    add_ticker(app, "SPIKE")  # the 5th asset, far above the others
    app.sidebar.radio(key="strategy").set_value("Normal").run()
    assert "Excluded as outliers" not in " ".join(c.value for c in app.caption)

    app.sidebar.toggle(key="exclude_outliers").set_value(True).run()
    assert not app.exception
    assert not app.warning
    assert app.slider(key="outlier_threshold").value == 3.5
    assert "Excluded as outliers at the latest rebalance: **SPIKE**" in " ".join(c.value for c in app.caption)

    app.slider(key="outlier_threshold").set_value(10.0).run()  # still far above
    assert "Excluded as outliers at the latest rebalance: **SPIKE**" in " ".join(c.value for c in app.caption)


def test_both_strategies_name_what_each_excluded(app):
    add_ticker(app, "SPIKE")
    app.sidebar.toggle(key="exclude_outliers").set_value(True).run()  # the app opens with both
    caption = " ".join(c.value for c in app.caption)
    assert "Excluded as outliers at the latest rebalance: **SPIKE (Normal); SPIKE (Volatility-adjusted)**" in caption


def test_outliers_need_at_least_four_assets(app):
    app.sidebar.toggle(key="exclude_outliers").set_value(True).run()  # the 4 default assets
    assert not app.warning

    app.sidebar.button[2].click().run()  # Clear
    app.session_state["pills_Equities"] = ["S&P 500", "Nasdaq 100"]
    app.run()
    assert [w.value for w in app.warning if w.value.startswith("Excluding outliers")] == [
        "Excluding outliers needs at least 4 ranked assets: with fewer, nothing is excluded."
    ]
    assert "st-key-outliers" in " ".join(m.value for m in app.markdown)
    assert "Excluded as outliers" not in " ".join(c.value for c in app.caption)


# ---- showing the assets on the main chart -----------------------------------


def chart_names(app) -> set[str]:
    """The names of the lines in the main chart."""
    return {t.get("name") for t in json.loads(app.get("plotly_chart")[0].proto.spec)["data"]}


def test_there_is_no_compare_to_benchmarks_toggle(app):
    assert not [t for t in app.sidebar.toggle if t.label == "Compare to benchmarks"]


def test_assets_are_shown_on_the_chart_by_default(app):
    assert app.sidebar.toggle(key="show_assets").value is True
    assert {"MSCI World (DM)", "Gold", "Bonds 7-10Y", "Bonds 0-1Y"} <= chart_names(app)


def test_hiding_the_assets_keeps_the_benchmark_and_the_strategies(app):
    app.sidebar.toggle(key="show_assets").set_value(False).run()
    assert not app.exception
    names = chart_names(app)
    assert not names & {"Gold", "Bonds 7-10Y", "Bonds 0-1Y"}
    # MSCI World is both a selected asset and the default benchmark, so it stays
    assert {"MSCI World (DM)", "Strategy (Normal)", "Strategy (Volatility-adjusted)"} <= names
    assert len(app.get("plotly_chart")) == 4  # drawdown and composition charts are unaffected

    app.sidebar.toggle(key="show_assets").set_value(True).run()
    assert {"Gold", "Bonds 7-10Y", "Bonds 0-1Y"} <= chart_names(app)


def test_hiding_the_assets_still_shows_a_benchmark_that_is_not_an_asset(app):
    app.sidebar.multiselect[0].set_value(["S&P 500"]).run()  # not one of the 4 default assets
    app.sidebar.toggle(key="show_assets").set_value(False).run()
    assert not app.exception
    names = chart_names(app)
    assert "S&P 500" in names
    assert not names & {"MSCI World (DM)", "Gold", "Bonds 7-10Y", "Bonds 0-1Y"}


def test_hiding_the_assets_without_benchmarks_leaves_only_the_strategies(app):
    app.sidebar.multiselect[0].set_value([]).run()
    app.sidebar.toggle(key="show_assets").set_value(False).run()
    assert not app.exception
    names = chart_names(app)
    assert {"Strategy (Normal)", "Strategy (Volatility-adjusted)"} <= names
    assert not names & {"MSCI World (DM)", "Gold", "Bonds 7-10Y", "Bonds 0-1Y"}
