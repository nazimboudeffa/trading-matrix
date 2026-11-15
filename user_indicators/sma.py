"""SMA — moyenne mobile simple (superposée au prix)."""

from __future__ import annotations

import pandas as pd

NAME = "SMA"
DESCRIPTION = "Moyenne mobile simple, superposée au prix."
PARAMS = {
    "period": {"type": "int", "default": 20, "min": 2, "max": 400, "label": "Période"},
    "color": {"type": "str", "default": "#f0b90b", "label": "Couleur"},
}


def compute(df: pd.DataFrame, period: int = 20, color: str = "#f0b90b"):
    from trading_matrix.indicators.base import IndicatorResult, PlotItem

    ma = df["Close"].rolling(window=int(period)).mean()
    return IndicatorResult(
        name=f"SMA({period})",
        kind="overlay",
        plots=[PlotItem(label=f"SMA({period})", series=ma, color=color, width=2)],
    )
