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


def test_currency_multiplies_the_prices_by_the_daily_rate(monkeypatch):
    index = pd.bdate_range("2020-01-01", periods=5)
    rate = pd.Series([0.9, 0.8, 0.5], index=index[[1, 2, 4]])  # EUR per USD; no rate on 2 days

    def fake_load(ticker):
        return rate if ticker == "EUR=X" else pd.Series(100.0, index=index)

    monkeypatch.setattr(data, "_load", fake_load)
    prices = data.load_prices(["SPY", data.CASH], "EUR")
    assert prices.index.equals(index[1:])  # no rate yet on the first day
    assert prices["SPY"].tolist() == pytest.approx([90, 80, 80, 50])  # a missing day keeps the last rate
    assert prices[data.CASH].tolist() == pytest.approx([0.9, 0.8, 0.8, 0.5])  # dollars move with the rate


def test_usd_needs_no_exchange_rate(monkeypatch):
    index = pd.bdate_range("2020-01-01", periods=3)

    def fake_load(ticker):
        assert not ticker.endswith("=X")
        return pd.Series(100.0, index=index)

    monkeypatch.setattr(data, "_load", fake_load)
    assert data.load_prices(["SPY"]).iloc[0, 0] == 100.0


def test_unknown_currency_is_refused():
    with pytest.raises(ValueError):
        data.load_prices(["SPY"], "XXX")


# ---- the currency a ticker is quoted in --------------------------------------

INDEX = pd.bdate_range("2020-01-01", periods=4)


def quoted_in(monkeypatch, quotes, rates):
    """Prices are 100 on every day; `rates` are the daily Yahoo rates (units per 1 USD)."""

    def fake_load(ticker):
        return pd.Series(rates[ticker] if ticker.endswith("=X") else 100.0, index=INDEX)

    monkeypatch.setattr(data, "_load", fake_load)
    monkeypatch.setattr(data, "_quote_currency", lambda t: quotes[t])


def test_a_ticker_quoted_in_euros_is_converted_to_usd(monkeypatch):
    quoted_in(monkeypatch, {"SAP.DE": "EUR"}, {"EUR=X": 0.8})  # 0.8 EUR per USD
    assert data.load_prices(["SAP.DE"])["SAP.DE"].tolist() == pytest.approx([125.0] * 4)


def test_a_ticker_is_converted_from_its_currency_to_the_chosen_one(monkeypatch):
    quoted_in(monkeypatch, {"PKO.WA": "PLN"}, {"PLN=X": 4.0, "GBP=X": 0.5})
    prices = data.load_prices(["PKO.WA"], "GBP")
    assert prices["PKO.WA"].tolist() == pytest.approx([12.5] * 4)  # 100 PLN = 25 USD = 12.5 GBP


def test_ticker_quoted_in_the_chosen_currency_is_not_converted(monkeypatch):
    quoted_in(monkeypatch, {"SAP.DE": "EUR"}, {})  # no rate needed
    assert data.load_prices(["SAP.DE"], "EUR")["SAP.DE"].tolist() == [100.0] * 4


def test_pence_are_divided_by_100(monkeypatch):
    quoted_in(monkeypatch, {"SHEL.L": "GBp"}, {"GBP=X": 0.5})
    assert data.load_prices(["SHEL.L"], "GBP")["SHEL.L"].tolist() == pytest.approx([1.0] * 4)
    assert data.load_prices(["SHEL.L"])["SHEL.L"].tolist() == pytest.approx([2.0] * 4)  # USD


def test_unknown_currency_is_taken_as_usd_and_reported(monkeypatch):
    quoted_in(monkeypatch, {"MYSTERY": None, "SPY": "USD"}, {})
    prices = data.load_prices(["MYSTERY", "SPY"])
    assert prices["MYSTERY"].tolist() == [100.0] * 4
    assert prices.attrs["unknown_currency"] == ["MYSTERY"]


def test_built_in_tickers_are_in_usd_without_asking_yahoo(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", None)  # any import would fail
    assert data._quote_currency("SPY") == "USD"
    assert data._quote_currency(data.CASH) == "USD"


def test_the_currency_from_yahoo_is_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    asked = []

    class FakeYahoo:
        class Ticker:
            def __init__(self, ticker):
                asked.append(ticker)
                self.fast_info = {"currency": "EUR"}

    monkeypatch.setitem(sys.modules, "yfinance", FakeYahoo)
    assert data._quote_currency("SAP.DE") == "EUR"
    assert data._quote_currency("SAP.DE") == "EUR"
    assert asked == ["SAP.DE"]


@pytest.mark.parametrize("answer", ["not a currency", None, 5])
def test_nonsense_from_yahoo_is_no_currency(monkeypatch, tmp_path, answer):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)

    class FakeYahoo:
        class Ticker:
            def __init__(self, ticker):
                self.fast_info = {"currency": answer}

    monkeypatch.setitem(sys.modules, "yfinance", FakeYahoo)
    assert data._quote_currency("XYZ") is None
    assert not list(tmp_path.iterdir())
