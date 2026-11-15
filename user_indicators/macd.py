"""MACD — Moving Average Convergence Divergence (sous-graphique)."""

from __future__ import annotations

import pandas as pd

NAME = "MACD"
DESCRIPTION = "Ligne MACD, ligne de signal et histogramme, en sous-graphique."
PARAMS = {
    "fast": {"type": "int", "default": 12, "min": 2, "max": 100, "label": "Rapide"},
    "slow": {"type": "int", "default": 26, "min": 5, "max": 200, "label": "Lente"},
    "signal": {"type": "int", "default": 9, "min": 2, "max": 100, "label": "Signal"},
}


def compute(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    from trading_matrix.indicators.base import IndicatorResult, PlotItem

    ema_fast = df["Close"].ewm(span=int(fast), adjust=False).mean()
    ema_slow = df["Close"].ewm(span=int(slow), adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=int(signal), adjust=False).mean()
    hist = macd_line - signal_line
    return IndicatorResult(
        name="MACD",
        kind="subplot",
        height=130,
        plots=[
            PlotItem(label="MACD", series=macd_line, color="#2962ff", width=1),
            PlotItem(label="Signal", series=signal_line, color="#f0b90b", width=1),
            PlotItem(label="Hist", series=hist, color="#787b86", width=1),
        ],
    )
