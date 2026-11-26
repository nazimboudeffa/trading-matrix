import pandas as pd
import pytest

from trading_matrix.strategies.base import Side, StrategyContext
from trading_matrix.strategies.engine import StrategyEngine
from trading_matrix.strategies.registry import StrategyRegistry
from user_strategies.annual_extremes import AnnualExtremes


def _prices():
    index = pd.date_range("2023-01-02", periods=400, freq="B")
    return pd.DataFrame({"High": 101., "Low": 99., "Close": 100.}, index=index)


def _run(df, timeframe="1d"):
    return AnnualExtremes().analyze(StrategyContext(df=df, timeframe=timeframe))


@pytest.mark.parametrize("side,close,high,low", [
    (Side.LONG, 103., 104., 99.), (Side.SHORT, 97., 101., 96.),
])
def test_confirmed_breakout_and_risk(side, close, high, low):
    df = _prices()
    df.iloc[-1] = [high, low, close]
    signals = _run(df)
    assert len(signals) == 1
    s = signals[0]
    assert s.side is side and s.time == df.index[-1]
    assert s.meta["annual_high"] == 101 and s.meta["annual_low"] == 99
    assert s.meta["rr"] == 2
    assert s.sl < s.entry < s.tp1 if side is Side.LONG else s.tp1 < s.entry < s.sl


def test_touch_or_wick_alone_is_not_a_breakout():
    df = _prices()
    df.iloc[-1] = [110., 90., 101.]
    assert _run(df) == []


def test_full_year_required():
    df = _prices().iloc[:240].copy()
    df.iloc[-1] = [104., 99., 103.]
    assert _run(df) == []


def test_old_extreme_expires_by_calendar_not_bar_count():
    df = _prices()
    df.iloc[0] = [500., 99., 100.]
    df.iloc[-1] = [104., 99., 103.]
    assert len(_run(df)) == 1


def test_recent_extreme_still_blocks_breakout():
    df = _prices()
    df.iloc[-100] = [120., 99., 100.]
    df.iloc[-1] = [104., 99., 103.]
    assert _run(df) == []


def test_sparse_history_does_not_count_as_a_full_year():
    df = _prices().iloc[::3].copy()
    df.iloc[-1] = [104., 99., 103.]
    assert _run(df) == []


def test_future_prices_do_not_change_past_signals():
    df = _prices()
    df.iloc[300] = [104., 99., 103.]
    before = _run(df.iloc[:320])
    df.iloc[-1] = [1000., 99., 900.]
    assert before and [s for s in _run(df) if s.time <= df.index[319]] == before


@pytest.mark.parametrize("mode", ["intraday", "weekly", "duplicate", "unsorted", "nan", "empty"])
def test_unsupported_or_invalid_data(mode):
    df = _prices()
    df.iloc[-1] = [104., 99., 103.]
    timeframe = "1d"
    if mode == "intraday":
        timeframe = "1h"
    elif mode == "weekly":
        timeframe = "1w"
    elif mode == "duplicate":
        df = pd.concat([df, df.iloc[-1:]])
    elif mode == "unsorted":
        df = df.iloc[::-1]
    elif mode == "nan":
        df.iloc[20, 0] = float("nan")
    else:
        df = df.iloc[:0]
    assert _run(df, timeframe) == []


def test_discovered_and_executable_through_engine():
    registry = StrategyRegistry()
    assert "annual_extremes" in registry.discover()
    df = _prices()
    df.iloc[-1] = [104., 99., 103.]
    assert len(StrategyEngine(registry).run("annual_extremes", df, timeframe="1d")) == 1
