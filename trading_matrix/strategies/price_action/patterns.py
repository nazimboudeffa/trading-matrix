import pandas as pd

from strategies import utils


def detect_reaction(df: pd.DataFrame, i: int) -> dict:
    """Détecte une réaction price action sur la bougie i."""
    out = {"bull": False, "bear": False, "types": []}
    if utils.is_bullish_engulfing(df, i):
        out["bull"] = True
        out["types"].append("BULL_ENGULFING")
    if utils.is_bearish_engulfing(df, i):
        out["bear"] = True
        out["types"].append("BEAR_ENGULFING")
    if utils.is_pinbar_bull(df, i):
        out["bull"] = True
        out["types"].append("PINBAR_BULL")
    if utils.is_pinbar_bear(df, i):
        out["bear"] = True
        out["types"].append("PINBAR_BEAR")
    return out
