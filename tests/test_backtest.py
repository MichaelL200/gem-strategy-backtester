import pandas as pd
import pytest

from gem_backtester.backtest import run


def make_prices() -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", "2021-12-31")
    half = len(index) // 2
    # A rises in the first half then falls; B is flat in the first half then rises.
    a = [100 * 1.001**i if i < half else 100 * 1.001**half * 0.999 ** (i - half) for i in range(len(index))]
    b = [100.0 if i < half else 100 * 1.002 ** (i - half) for i in range(len(index))]
    return pd.DataFrame({"A": a, "B": b}, index=index)


def make_monthly_steps() -> pd.DataFrame:
    """A gains 2% a month until Oct 2021, then drops 20% in Nov. B is flat."""
    index = pd.bdate_range("2020-01-01", "2021-11-30")
    k = (index.year - 2020) * 12 + index.month - 1
    a = [100 * 1.02 ** min(m, 21) * (0.8 if m == 22 else 1.0) for m in k]
    return pd.DataFrame({"A": a, "B": 100.0}, index=index)


def test_picks_best_in_window():
    result = run(make_prices(), 3)
    assert result.picks.iloc[0] == "A"
    assert result.picks.iloc[-1] == "B"


def test_equity_starts_at_one_and_assets_are_included():
    result = run(make_prices(), 3)
    assert result.equity.iloc[0] == 1.0
    assert list(result.assets.columns) == ["A", "B"]
    assert (result.assets.iloc[0] == 1.0).all()


def test_ignored_months_change_the_pick():
    prices = make_monthly_steps()
    assert run(prices, 3, skip=0).picks.iloc[-1] == "B"  # the Nov drop is inside the window
    assert run(prices, 3, skip=1).picks.iloc[-1] == "A"  # the Nov drop is ignored


def test_skip_must_be_shorter_than_lookback():
    with pytest.raises(ValueError):
        run(make_prices(), 3, skip=3)


def test_missing_day_does_not_change_picks():
    prices = make_prices()
    gapped = prices.copy()
    gapped.loc["2020-09-30", "A"] = float("nan")
    pd.testing.assert_series_equal(run(prices, 3).picks, run(gapped, 3).picks)


def test_no_lookahead():
    prices = make_prices()
    cutoff = pd.Timestamp("2021-06-30")
    base = run(prices.loc[:cutoff], 3)
    wrecked = prices.copy()
    wrecked.loc[wrecked.index > cutoff] = 1.0
    other = run(wrecked, 3)
    pd.testing.assert_series_equal(base.equity.loc[:cutoff], other.equity.loc[:cutoff])


def test_not_enough_history():
    with pytest.raises(ValueError):
        run(make_prices(), 24)


def test_late_asset_joins_when_it_has_history():
    prices = make_prices()
    prices.loc[prices.index[:300], "B"] = float("nan")
    result = run(prices, 3)
    assert result.picks.iloc[0] == "A"
    assert result.picks.index[0] < prices.index[300]


def test_late_asset_line_starts_at_strategy_value():
    prices = make_prices()
    prices.loc[prices.index[:300], "B"] = float("nan")
    result = run(prices, 3)
    first = result.assets["B"].first_valid_index()
    assert first == prices.index[300]
    assert result.assets.loc[first, "B"] == pytest.approx(result.equity.loc[first])


def late_b_prices() -> pd.DataFrame:
    prices = make_prices()
    prices.loc[prices.index[:300], "B"] = float("nan")
    return prices


def test_common_period_starts_when_every_asset_is_eligible():
    prices = late_b_prices()
    everything = run(prices, 3)
    common = run(prices, 3, common=True)
    assert common.picks.index[0] > everything.picks.index[0]
    assert common.picks.index[0] > prices.index[300]  # B has a full 3-month window by then
    assert set(common.assets.columns) == {"A", "B"}


def test_custom_period_bounds():
    prices = make_prices()
    result = run(prices, 3, start="2020-12-31", end="2021-09-30")
    assert result.start == pd.Timestamp("2020-12-31")
    assert result.end <= pd.Timestamp("2021-09-30")


def test_custom_start_uses_earlier_history_for_first_signal():
    prices = make_prices()
    # The first pick on 2020-12-31 is based on the 3 months before the start date.
    result = run(prices, 3, start="2020-12-31")
    assert result.picks.index[0] == pd.Timestamp("2020-12-31")
    assert result.picks.iloc[0] == run(prices, 3).picks.loc["2020-12-31"]


def test_end_date_has_no_lookahead():
    prices = make_prices()
    wrecked = prices.copy()
    wrecked.loc[wrecked.index > "2021-06-30"] = 1.0
    a = run(prices, 3, end="2021-06-30")
    b = run(wrecked, 3, end="2021-06-30")
    pd.testing.assert_series_equal(a.equity, b.equity)


def test_period_without_data_raises():
    with pytest.raises(ValueError):
        run(make_prices(), 3, start="2030-01-01")
    with pytest.raises(ValueError):
        run(make_prices(), 3, end="2019-01-01")
