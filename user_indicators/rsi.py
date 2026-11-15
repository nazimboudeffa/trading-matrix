"""RSI — Relative Strength Index (sous-graphique)."""

from __future__ import annotations

import pandas as pd

NAME = "RSI"
DESCRIPTION = "Relative Strength Index, affiché en sous-graphique (zones 70/30)."
PARAMS = {
    "period": {"type": "int", "default": 14, "min": 2, "max": 100, "label": "Période"},
}


def compute(df: pd.DataFrame, period: int = 14):
    from trading_matrix.indicators.base import IndicatorResult, PlotItem

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(window=int(period)).mean()
    loss = (-delta.clip(upper=0)).rolling(window=int(period)).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return IndicatorResult(
        name=f"RSI({period})",
        kind="subplot",
        height=110,
        plots=[PlotItem(label="RSI", series=rsi, color="#9c27b0", width=1)],
        hlines=[(70, "#ef5350"), (30, "#26a69a")],
    )
