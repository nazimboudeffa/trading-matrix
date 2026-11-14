from dataclasses import dataclass
from typing import Literal

import pandas as pd

Trend = Literal["BULLISH", "BEARISH", "RANGE"]


@dataclass
class Swing:
    index: int
    price: float
    kind: Literal["HIGH", "LOW"]
    confirmed: bool = True


def find_swings(df: pd.DataFrame, left: int = 3, right: int = 3) -> list[Swing]:
    swings: list[Swing] = []
    n = len(df)
    if n < left + right + 1:
        return swings

    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)

    for i in range(left, n - right):
        left_h = highs[i - left : i]
        right_h = highs[i + 1 : i + right + 1]
        if highs[i] >= left_h.max() and highs[i] >= right_h.max():
            swings.append(Swing(index=i, price=float(highs[i]), kind="HIGH"))

        left_l = lows[i - left : i]
        right_l = lows[i + 1 : i + right + 1]
        if lows[i] <= left_l.min() and lows[i] <= right_l.min():
            swings.append(Swing(index=i, price=float(lows[i]), kind="LOW"))

    swings.sort(key=lambda s: s.index)
    return swings


def get_trend(swings: list[Swing]) -> Trend:
    if len(swings) < 4:
        return "RANGE"
    highs = [s for s in swings if s.kind == "HIGH"][-3:]
    lows = [s for s in swings if s.kind == "LOW"][-3:]
    if len(highs) >= 2 and len(lows) >= 2:
        if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
            return "BULLISH"
        if highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
            return "BEARISH"
    return "RANGE"


def detect_bos_choch(df: pd.DataFrame, swings: list[Swing]) -> dict:
    """Détection simplifiée BOS/CHOCH basée sur cassure de dernier swing structurel."""
    res = {"bos": None, "choch": None, "last_bullish": None, "last_bearish": None}
    if len(swings) < 4:
        return res
    # Derniers swings significatifs
    recent = swings[-6:]
    for s in recent:
        if s.kind == "HIGH":
            res["last_bullish"] = s
        if s.kind == "LOW":
            res["last_bearish"] = s
    # Vérifier cassure récente
    if res["last_bearish"] and len(df) > res["last_bearish"].index:
        if df["Close"].iloc[-1] > res["last_bearish"].price:
            res["bos"] = {"type": "BOS", "dir": "BULL", "level": res["last_bearish"].price}
    if res["last_bullish"] and len(df) > res["last_bullish"].index:
        if df["Close"].iloc[-1] < res["last_bullish"].price:
            res["choch"] = {"type": "CHOCH", "dir": "BEAR", "level": res["last_bullish"].price}
    return res
