"""EMA — moyenne mobile exponentielle (superposée au prix)."""

from __future__ import annotations

import pandas as pd

NAME = "EMA"
DESCRIPTION = "Moyenne mobile exponentielle, superposée au prix."
PARAMS = {
    "period": {"type": "int", "default": 50, "min": 2, "max": 400, "label": "Période"},
    "color": {"type": "str", "default": "#2962ff", "label": "Couleur"},
}


def compute(df: pd.DataFrame, period: int = 50, color: str = "#2962ff"):
    from trading_matrix.indicators.base import IndicatorResult, PlotItem

    ema = df["Close"].ewm(span=int(period), adjust=False).mean()
    return IndicatorResult(
        name=f"EMA({period})",
        kind="overlay",
        plots=[PlotItem(label=f"EMA({period})", series=ema, color=color, width=2)],
    )
