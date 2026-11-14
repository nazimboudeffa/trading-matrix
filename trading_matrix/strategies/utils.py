import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def body(df: pd.DataFrame) -> pd.Series:
    return (df["Close"] - df["Open"]).abs()


def range_hl(df: pd.DataFrame) -> pd.Series:
    return df["High"] - df["Low"]


def is_bullish_engulfing(df: pd.DataFrame, i: int) -> bool:
    if i < 1:
        return False
    prev = df.iloc[i - 1]
    cur = df.iloc[i]
    return prev["Close"] < prev["Open"] and cur["Close"] > cur["Open"] and cur["Close"] >= prev["Open"] and cur["Open"] <= prev["Close"]


def is_bearish_engulfing(df: pd.DataFrame, i: int) -> bool:
    if i < 1:
        return False
    prev = df.iloc[i - 1]
    cur = df.iloc[i]
    return prev["Close"] > prev["Open"] and cur["Close"] < cur["Open"] and cur["Close"] <= prev["Open"] and cur["Open"] >= prev["Close"]


def is_pinbar_bull(df: pd.DataFrame, i: int, ratio: float = 2.0) -> bool:
    if i < 0:
        return False
    c = df.iloc[i]
    rng = range_hl(df).iloc[i]
    if rng == 0:
        return False
    b = body(df).iloc[i]
    lower_wick = min(c["Open"], c["Close"]) - c["Low"]
    return lower_wick >= ratio * b and lower_wick > (rng - lower_wick)


def is_pinbar_bear(df: pd.DataFrame, i: int, ratio: float = 2.0) -> bool:
    if i < 0:
        return False
    c = df.iloc[i]
    rng = range_hl(df).iloc[i]
    if rng == 0:
        return False
    b = body(df).iloc[i]
    upper_wick = c["High"] - max(c["Open"], c["Close"])
    return upper_wick >= ratio * b and upper_wick > (rng - upper_wick)
