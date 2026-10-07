import pytest

from gem_backtester.assets import normalize_ticker


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
