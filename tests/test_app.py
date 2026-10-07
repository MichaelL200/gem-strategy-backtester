from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gem_backtester import data
from gem_backtester.assets import ASSETS, CATEGORIES

APP = str(Path(__file__).parent.parent / "app.py")


@pytest.fixture
def app(monkeypatch):
    index = pd.bdate_range("2015-01-01", "2024-12-31")
    rng = np.random.default_rng(0)

    def fake_load(ticker):
        if ticker == "NOPE":
            raise ValueError("No price data for NOPE")
        return pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(index))), index=index)

    monkeypatch.setattr(data, "_load", fake_load)
    return AppTest.from_file(APP, default_timeout=60).run()


def selected(app) -> dict[str, list[str]]:
    return {g.key.removeprefix("pills_"): g.value for g in app.sidebar.button_group}


def test_select_all_and_clear(app):
    app.sidebar.button[0].click().run()  # Select all
    assert not app.exception
    assert selected(app) == {category: list(group) for category, group in CATEGORIES.items()}
    assert app.slider(key="top_n").max == len(ASSETS)

    app.sidebar.button[1].click().run()  # Clear
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
    app.sidebar.button[1].click().run()  # Clear
    app.session_state["pills_Equities"] = ["S&P 500"]
    app.run()
    assert not app.exception
    assert len(app.warning) == 1
    assert app.warning[0].value.startswith("Only one asset is selected")
    assert "st-key-assets" in " ".join(m.value for m in app.markdown)
    assert not [s for s in app.slider if s.key == "top_n"]  # nothing to choose between
    assert len(app.metric) == 6
    assert len(app.get("plotly_chart")) == 3
    assert "Latest pick: **S&P 500**" in " ".join(c.value for c in app.caption)


def add_ticker(app, text):
    app.text_input(key="new_ticker").set_value(text)
    app.sidebar.button[2].click().run()  # the form's "Add" button (after Select all and Clear)


def test_custom_ticker_is_added_and_selected(app):
    add_ticker(app, " nvda ")
    assert not app.exception
    assert not app.warning
    assert selected(app)["Custom"] == ["NVDA"]
    assert len(app.metric) == 6  # the backtest runs with the new asset

    app.sidebar.button[1].click().run()  # Clear
    assert selected(app)["Custom"] == []
    app.sidebar.button[0].click().run()  # Select all
    assert selected(app)["Custom"] == ["NVDA"]


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
