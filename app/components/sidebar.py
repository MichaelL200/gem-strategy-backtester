"""Shared sidebar helpers for the Streamlit application."""

import pandas as pd
import streamlit as st

from data import load_prices


def is_mobile() -> bool:
    """Return whether the current request identifies a mobile browser."""
    try:
        return "Mobi" in st.context.headers.get("User-Agent", "")
    except Exception:
        return False


def highlight(key: str, color: str = "#FFA000") -> None:
    """Highlight a sidebar setting associated with a warning."""
    st.markdown(
        f"<style>.st-key-{key}{{outline:2px solid {color};outline-offset:6px;border-radius:6px}}</style>",
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=12 * 3600)
def prices_for(tickers: tuple[str, ...], currency: str) -> pd.DataFrame:
    """Load and cache the prices used by the sidebar configuration."""
    return load_prices(list(tickers), currency)
