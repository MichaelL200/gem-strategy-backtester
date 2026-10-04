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
    assert result.picks.iloc[0] == ["A"]
    assert result.picks.iloc[-1] == ["B"]


def test_equity_starts_at_one_and_assets_are_included():
    result = run(make_prices(), 3)
    assert result.equity.iloc[0] == 1.0
    assert list(result.assets.columns) == ["A", "B"]
    assert (result.assets.iloc[0] == 1.0).all()


def test_ignored_months_change_the_pick():
    prices = make_monthly_steps()
    assert run(prices, 3, skip=0).picks.iloc[-1] == ["B"]  # the Nov drop is inside the window
    assert run(prices, 3, skip=1).picks.iloc[-1] == ["A"]  # the Nov drop is ignored


def test_skip_must_be_shorter_than_lookback():
    with pytest.raises(ValueError):
        run(make_prices(), 3, skip=3)


def test_missing_day_does_not_change_picks():
    prices = make_prices()
    gapped = prices.copy()
    gapped.loc["2020-09-30", "A"] = float("nan")
    # Compare element-wise since picks are lists
    for a, b in zip(run(prices, 3).picks, run(gapped, 3).picks):
        assert a == b


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
    assert result.picks.iloc[0] == ["A"]
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


# ---- top_n tests -----------------------------------------------------------

def test_top_n_one_is_default_behaviour():
    """top_n=1 must match the legacy single-winner behaviour."""
    prices = make_prices()
    result_default = run(prices, 3)
    result_explicit = run(prices, 3, top_n=1)
    pd.testing.assert_series_equal(result_default.equity, result_explicit.equity)
    for a, b in zip(result_default.picks, result_explicit.picks):
        assert a == b


def test_top_n_picks_contains_n_tickers():
    prices = make_prices()
    result = run(prices, 3, top_n=2)
    for pick_list in result.picks:
        assert len(pick_list) == 2


def test_top_n_weights_drift_between_rebalances():
    """No trading between rebalances: each asset keeps its units, so the weights drift."""
    prices = make_prices()
    result = run(prices, 3, rebalance=12, top_n=2)
    first, second = result.picks.index[:2]
    days = result.equity.loc[first:second].index
    expected = 0.5 * prices.loc[days, "A"] / prices.loc[first, "A"]
    expected += 0.5 * prices.loc[days, "B"] / prices.loc[first, "B"]
    pd.testing.assert_series_equal(result.equity.loc[first:second], expected, check_names=False, check_freq=False)


def test_top_n_weights_are_equal_again_at_each_rebalance():
    prices = make_prices()
    result = run(prices, 3, rebalance=3, top_n=2)
    second, third = result.picks.index[1:3]
    days = result.equity.loc[second:third].index
    growth = result.equity.loc[days] / result.equity[second]
    expected = 0.5 * prices.loc[days, "A"] / prices.loc[second, "A"]
    expected += 0.5 * prices.loc[days, "B"] / prices.loc[second, "B"]
    pd.testing.assert_series_equal(growth, expected, check_names=False, check_freq=False)


def test_rebalance_period_matters_when_holding_all_assets():
    prices = make_prices()
    monthly = run(prices, 3, rebalance=1, top_n=2).equity
    yearly = run(prices, 3, rebalance=12, top_n=2).equity
    assert monthly.iloc[-1] != pytest.approx(yearly.iloc[-1])


def test_top_n_holds_only_assets_that_can_be_ranked():
    """An asset without history has no momentum: it must not be picked, nor take a share."""
    prices = make_prices()
    prices.loc[prices.index[:300], "B"] = float("nan")
    result = run(prices, 3, top_n=2)
    first = result.picks.index[0]
    assert result.picks.iloc[0] == ["A"]
    day = result.equity.index[10]  # before B has prices
    assert result.equity[day] == pytest.approx(prices.loc[day, "A"] / prices.loc[first, "A"])
    assert result.equity.min() > 0.5


def test_top_n_greater_than_assets_is_capped():
    """top_n larger than the asset count should not raise; it just holds all available assets."""
    prices = make_prices()  # 2 assets
    result = run(prices, 3, top_n=10)
    for pick_list in result.picks:
        assert len(pick_list) <= 2


def test_top_n_must_be_at_least_one():
    with pytest.raises(ValueError):
        run(make_prices(), 3, top_n=0)


def test_top_n_slow_rebalance():
    """top_n interacts correctly with multi-month rebalancing intervals."""
    prices = make_prices()
    result = run(prices, 3, rebalance=3, top_n=2)
    for pick_list in result.picks:
        assert len(pick_list) == 2
    assert list(result.picks.index) == list(run(prices, 3, rebalance=3).picks.index)


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


def test_monthly_is_the_default_rebalance():
    prices = make_prices()
    pd.testing.assert_series_equal(run(prices, 3).picks, run(prices, 3, rebalance=1).picks)


def test_rebalance_every_n_months_spaces_the_picks():
    prices = make_prices()
    monthly = run(prices, 3)
    quarterly = run(prices, 3, rebalance=3)
    assert quarterly.picks.index[0] == monthly.picks.index[0]
    assert list(quarterly.picks.index) == list(monthly.picks.index[::3])
    assert quarterly.picks.equals(monthly.picks.iloc[::3])


def test_slow_rebalance_does_not_react_between_rebalances():
    # A gains 2% a month until Oct 2021, then drops 20% in Nov; B is flat.
    prices = make_monthly_steps()
    monthly = run(prices, 3, skip=0)
    slow = run(prices, 3, skip=0, rebalance=12)
    # Monthly sees the drop at the Nov month-end; the 12-month cycle's last rebalance is earlier,
    # so it still points at A.
    assert monthly.picks.iloc[-1] == ["B"]
    assert slow.picks.index[-1] < monthly.picks.index[-1]
    assert slow.picks.iloc[-1] == ["A"]


def test_rebalance_has_no_lookahead():
    prices = make_prices()
    cutoff = pd.Timestamp("2021-06-30")
    base = run(prices.loc[:cutoff], 3, rebalance=2)
    wrecked = prices.copy()
    wrecked.loc[wrecked.index > cutoff] = 1.0
    other = run(wrecked, 3, rebalance=2)
    pd.testing.assert_series_equal(base.equity.loc[:cutoff], other.equity.loc[:cutoff])


def test_rebalance_must_be_at_least_one_month():
    with pytest.raises(ValueError):
        run(make_prices(), 3, rebalance=0)
