"""Bandes de Bollinger (superposées au prix)."""

from __future__ import annotations

import pandas as pd

NAME = "Bandes de Bollinger"
DESCRIPTION = "Moyenne mobile et écarts-types autour du prix."
PARAMS = {
    "period": {"type": "int", "default": 20, "min": 5, "max": 200, "label": "Période"},
    "std": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "step": 0.5, "label": "Écart-type"},
}


def compute(df: pd.DataFrame, period: int = 20, std: float = 2.0):
    from trading_matrix.indicators.base import IndicatorResult, PlotItem

    ma = df["Close"].rolling(window=int(period)).mean()
    sd = df["Close"].rolling(window=int(period)).std()
    upper = ma + float(std) * sd
    lower = ma - float(std) * sd
    return IndicatorResult(
        name=f"Bollinger({period}, {std})",
        kind="overlay",
        plots=[
            PlotItem(label="BB haut", series=upper, color="#787b86", width=1),
            PlotItem(label="BB milieu", series=ma, color="#2962ff", width=1),
            PlotItem(label="BB bas", series=lower, color="#787b86", width=1),
        ],
    )
