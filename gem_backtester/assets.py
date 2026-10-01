"""Selectable assets by category: name -> ETF ticker (adjusted close, so dividends are included)."""

CATEGORIES = {
    "Equities": {
        "S&P 500": "SPY",
        "Nasdaq 100": "QQQ",
        "MSCI World": "URTH",
        "MSCI ACWI": "ACWI",
        "MSCI EM": "EEM",
        "MSCI DM": "EFA",
    },
    "Commodities": {
        "Gold": "GLD",
        "Silver": "SLV",
    },
    "Bonds": {
        "Bonds 7-10Y": "IEF",
        "Bonds 20Y+": "TLT",
        "Aggregate Bonds": "AGG",
    },
    "Cash": {
        "T-Bills 1-3M": "BIL",
        "Bonds 0-1Y": "SHV",
    },
}

ASSETS = {name: ticker for group in CATEGORIES.values() for name, ticker in group.items()}
