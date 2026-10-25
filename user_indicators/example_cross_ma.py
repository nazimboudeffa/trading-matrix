import pandas as pd

NAME = "Croisement MA Rapide/Lente"
DESCRIPTION = "Affiche SMA rapide et lente"
PARAMS = {"fast": 10, "slow": 30}


def compute(df: pd.DataFrame, fast: int = 10, slow: int = 30):
    from indicators.base import IndicatorResult, PlotItem

    sma_fast = df["Close"].rolling(fast).mean()
    sma_slow = df["Close"].rolling(slow).mean()

    return IndicatorResult(
        name=f"MA Croisement ({fast}/{slow})",
        kind="overlay",
        plots=[
            PlotItem(label=f"SMA{fast}", series=sma_fast, color="#f0b90b", width=2),
            PlotItem(label=f"SMA{slow}", series=sma_slow, color="#2962ff", width=2),
        ],
    )
