import pytest

from gem_backtester.assets import normalize_ticker, split_tickers


@pytest.mark.parametrize(
    ("text", "ticker"),
    [
        (" nvda ", "NVDA"),
        ("^gspc", "^GSPC"),
        ("eurusd=x", "EURUSD=X"),
        ("BRK-B", "BRK-B"),
        ("sap.de", "SAP.DE"),
    ],
)
def test_normalize_ticker(text, ticker):
    assert normalize_ticker(text) == ticker


@pytest.mark.parametrize("text", ["", "  ", "a/b", "a b", "..\\x", "C:", "x" * 16, "ä"])
def test_normalize_ticker_refuses_other_text(text):
    with pytest.raises(ValueError):
        normalize_ticker(text)


@pytest.mark.parametrize(
    ("text", "tickers"),
    [
        ("NVDA", ["NVDA"]),
        ("NVDA AAPL  MSFT", ["NVDA", "AAPL", "MSFT"]),
        ("NVDA,AAPL, MSFT", ["NVDA", "AAPL", "MSFT"]),
        ("NVDA;AAPL | MSFT", ["NVDA", "AAPL", "MSFT"]),
        ("NVDA\nAAPL\r\nMSFT\tTSLA", ["NVDA", "AAPL", "MSFT", "TSLA"]),
        ('"NVDA", \'AAPL\', [MSFT], $TSLA', ["NVDA", "AAPL", "MSFT", "TSLA"]),
        ("^GSPC, EURUSD=X, BRK-B, SAP.DE", ["^GSPC", "EURUSD=X", "BRK-B", "SAP.DE"]),
        ("nvda NVDA Nvda aapl", ["nvda", "aapl"]),  # repeats dropped, first spelling kept
        ("a/b", ["a/b"]),  # not a separator: refused later by normalize_ticker
        ("", []),
        (" ,;|\n ", []),
    ],
)
def test_split_tickers(text, tickers):
    assert split_tickers(text) == tickers
