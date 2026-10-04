"""Selectable assets by category: name -> ETF ticker (adjusted close, so dividends are included).

"USD" is not an ETF: it is plain cash in dollars (price 1.0, return 0%), see data.py.
"""

CATEGORIES = {
    "Equities": {
        "S&P 500": "SPY",
        "Nasdaq 100": "QQQ",
        "MSCI World (DM)": "URTH",
        "MSCI ACWI": "ACWI",
        "MSCI EM": "EEM",
        "MSCI EAFE": "EFA",
        "MSCI Europe": "IEUR",
        "MSCI Asia ex-Japan": "AAXJ",
        "S&P Latin America 40": "ILF",
        "MSCI Poland": "EPOL",
    },
    "Commodities": {
        "Gold": "GLD",
        "Silver": "SLV",
        "Broad Commodities": "DBC",
    },
    "Real Estate": {
        "Vanguard Real Estate": "VNQ",
    },
    "Bonds": {
        "Bonds 7-10Y": "IEF",
        "Bonds 20Y+": "TLT",
        "Aggregate Bonds": "AGG",
        "TIPS": "TIP",
    },
    "Cash": {
        "Cash (USD)": "USD",
        "T-Bills 1-3M": "BIL",
        "Bonds 0-1Y": "SHV",
    },
}

ASSETS = {name: ticker for group in CATEGORIES.values() for name, ticker in group.items()}
