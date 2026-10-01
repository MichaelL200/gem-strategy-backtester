import pandas as pd
import pytest

from gem_backtester.periods import availability, duration_text, window_months, window_text


def test_default_window_is_eleven_months():
    assert window_months(12, 1) == 11
    assert window_text(12, 1) == "11 months"
    assert window_text(2, 1) == "1 month"


@pytest.mark.parametrize(
    ("start", "end", "text"),
    [
        ("2020-01-31", "2020-12-31", "11 months"),
        ("2013-01-31", "2026-10-01", "13 years 8 months"),
        ("2020-01-01", "2021-01-01", "1 year"),
        ("2020-01-01", "2022-02-01", "2 years 1 month"),
        ("2020-01-01", "2020-01-21", "20 days"),
    ],
)
def test_duration_text(start, end, text):
    assert duration_text(start, end) == text


def test_duration_rejects_reversed_dates():
    with pytest.raises(ValueError):
        duration_text("2021-01-01", "2020-01-01")


def test_availability_shows_when_each_asset_can_be_ranked():
    index = pd.bdate_range("2020-01-01", "2021-12-31")
    prices = pd.DataFrame({"A": 100.0, "B": 100.0}, index=index)
    prices.loc[index[:300], "B"] = float("nan")
    table = availability(prices, 3, 0)
    assert table.loc["A", "First price"] == index[0]
    assert table.loc["B", "First price"] == index[300]
    assert table.loc["B", "Ranked from"] > table.loc["A", "Ranked from"]
