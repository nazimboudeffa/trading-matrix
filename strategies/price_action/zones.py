from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class Zone:
    kind: Literal["OB_BULL", "OB_BEAR", "LIQ"]
    top: float
    bottom: float
    index: int
    mitigated: bool = False
    strength: int = 50


def find_order_blocks(df: pd.DataFrame, lookback: int = 50) -> list[Zone]:
    """Détection simplifiée d'Order Blocks.

    Bullish OB : dernière bougie baissière avant une impulsion haussière
    qui clôture au-dessus du haut de cette bougie.
    Bearish OB : symétrique.
    """
    zones: list[Zone] = []
    n = len(df)
    if n < 5:
        return zones

    o = df["Open"].to_numpy(dtype=float)
    h = df["High"].to_numpy(dtype=float)
    l = df["Low"].to_numpy(dtype=float)
    c = df["Close"].to_numpy(dtype=float)

    ranges = h - l
    avg_range = float(np.nanmean(ranges[-50:])) if n else 0.0
    if not np.isfinite(avg_range) or avg_range <= 0:
        avg_range = 0.0

    start = max(1, n - lookback)
    for i in range(start, n - 1):
        cur_bear = c[i] < o[i]
        cur_bull = c[i] > o[i]
        nxt_bull = c[i + 1] > o[i + 1]
        nxt_bear = c[i + 1] < o[i + 1]

        # Bullish OB
        if cur_bear and nxt_bull and c[i + 1] > h[i]:
            displacement = (h[i + 1] - l[i + 1]) if i + 1 < n else 0.0
            if displacement >= 0.6 * avg_range:
                zones.append(
                    Zone(
                        kind="OB_BULL",
                        top=float(max(o[i], c[i])),
                        bottom=float(l[i]),
                        index=i,
                        strength=65,
                    )
                )

        # Bearish OB
        if cur_bull and nxt_bear and c[i + 1] < l[i]:
            displacement = (h[i + 1] - l[i + 1]) if i + 1 < n else 0.0
            if displacement >= 0.6 * avg_range:
                zones.append(
                    Zone(
                        kind="OB_BEAR",
                        top=float(h[i]),
                        bottom=float(min(o[i], c[i])),
                        index=i,
                        strength=65,
                    )
                )

    return zones


def is_price_in_zone(price: float, zone: Zone) -> bool:
    return zone.bottom <= price <= zone.top


def mitigate_zones(zones: list[Zone], df: pd.DataFrame) -> list[Zone]:
    if not zones:
        return zones
    for z in zones:
        for i in range(z.index + 1, len(df)):
            if df["Low"].iloc[i] <= z.top and df["High"].iloc[i] >= z.bottom:
                z.mitigated = True
                break
    return zones
