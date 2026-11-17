"""La stratégie EMA doit se comporter comme une stratégie complète (modèle SMA)."""

import numpy as np
import pandas as pd

from trading_matrix.strategies.base import Side, StrategyContext
from user_strategies.ema_crossover import EmaCrossover


def _ohlcv() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    close = np.r_[
        100 + rng.normal(0, 0.2, 80),
        100 + np.linspace(0, 20, 60) + rng.normal(0, 0.2, 60),
        120 - np.linspace(0, 20, 60) + rng.normal(0, 0.2, 60),
    ]
    op = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "Open": op,
            "High": np.maximum(op, close) + 0.3,
            "Low": np.minimum(op, close) - 0.3,
            "Close": close,
        },
        index=pd.date_range("2024-01-01", periods=len(close), freq="h"),
    )


def _run(df: pd.DataFrame, **params) -> list:
    return EmaCrossover().analyze(StrategyContext(df=df, params=params))


def test_crosses_give_coherent_signals() -> None:
    signals = _run(_ohlcv())

    assert any(s.setup_type == "EMA_BULLISH_CROSS" for s in signals)
    assert any(s.setup_type == "EMA_BEARISH_CROSS" for s in signals)
    for sig in signals:
        is_long = sig.side is Side.LONG
        assert sig.setup_type == ("EMA_BULLISH_CROSS" if is_long else "EMA_BEARISH_CROSS")
        if is_long:
            assert sig.sl < sig.entry < sig.tp1 < sig.tp2 < sig.tp3
        else:
            assert sig.sl > sig.entry > sig.tp1 > sig.tp2 > sig.tp3
        assert sig.meta["rr"] > 0
        assert sig.meta["atr"] > 0
        assert np.isfinite(sig.meta["ema_fast"])
        assert np.isfinite(sig.meta["ema_slow"])


def test_cooldown_reduces_signal_count() -> None:
    df = _ohlcv()

    assert len(_run(df, cooldown=20)) < len(_run(df, cooldown=0))


def test_trend_filter_only_keeps_aligned_signals() -> None:
    df = _ohlcv()

    signals = _run(df, trend_filter=True)

    assert signals
    for sig in signals:
        slope = sig.meta["slope_slow_atr"]
        if slope is None or not np.isfinite(slope):
            continue
        assert (sig.side is Side.LONG and slope > 0) or (sig.side is Side.SHORT and slope < 0)


def test_empty_frame_has_no_signal() -> None:
    assert _run(pd.DataFrame(columns=["High", "Low", "Close"])) == []
