import sys

import pandas as pd
import pytest

from gem_backtester import data
from gem_backtester.assets import ASSETS


def test_tickers_are_unique():
    assert len(set(ASSETS.values())) == len(ASSETS)


def test_cash_is_flat_and_keeps_requested_order(monkeypatch):
    index = pd.bdate_range("2020-01-01", periods=5)
    monkeypatch.setattr(data, "_load", lambda t: pd.Series(range(1, 6), index=index, dtype=float))
    prices = data.load_prices(["SPY", data.CASH, "GLD"])
    assert list(prices.columns) == ["SPY", data.CASH, "GLD"]
    assert (prices[data.CASH] == 1.0).all()
    assert prices.index.equals(index)


def test_duplicate_dates_are_dropped(monkeypatch, tmp_path):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    (tmp_path / "IEUR.csv").write_text("Date,IEUR\n2020-01-01,10\n2020-01-02,11\n2020-01-02,12\n")
    prices = data.load_prices(["IEUR", data.CASH])
    assert prices.index.is_unique
    assert prices["IEUR"].iloc[-1] == 12


@pytest.mark.parametrize(
    "content",
    [
        "Date,DBC\n2020-01-01,10\n2020-01-02,11,99\n",  # a line with an extra field
        "Date,DBC\nTicker,DBC\n2020-01-01,10\n2020-01-02,11\n",  # a row that is not a date
        "Date,DBC\n2020-01-01,10\n2020-01-02,abc\n",  # a price that is not a number
    ],
)
def test_damaged_cache_is_downloaded_again(monkeypatch, tmp_path, content):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    (tmp_path / "DBC.csv").write_text(content)
    index = pd.bdate_range("2020-01-01", periods=3)

    class FakeYahoo:
        @staticmethod
        def download(*args, **kwargs):
            return pd.DataFrame({"Close": [1.0, 2.0, 3.0]}, index=index)

    monkeypatch.setitem(sys.modules, "yfinance", FakeYahoo)
    prices = data.load_prices(["DBC", data.CASH])
    assert list(prices["DBC"]) == [1.0, 2.0, 3.0]
    assert isinstance(prices.index, pd.DatetimeIndex)
    assert not list(tmp_path.glob("*.tmp"))
