"""Cassure à la clôture des extrêmes des 52 semaines précédentes.

Bougies journalières uniquement. Fenêtre de 364 jours calendaires, bougie
courante exclue, historique couvrant au moins cette durée et 200 observations.
Les signaux sont confirmés à la clôture ; l'entrée indiquée est cette clôture
théorique, sans simulation d'exécution, de frais ou de performance.
"""

import numpy as np
import pandas as pd

from trading_matrix.strategies.base import BaseStrategy, Side, Signal, StrategyContext
from trading_matrix.strategies.utils import atr


class AnnualExtremes(BaseStrategy):
    id = "annual_extremes"
    name = "Extrêmes annuels (52 semaines)"
    display_order = 40
    description = (
        "Cassure en clôture du plus haut/bas des 52 semaines précédentes. "
        "Bougies 1d et historique supérieur à 52 semaines requis ; SL/TP par ATR."
    )
    params_schema = {
        "sl_atr": {"type": "float", "default": 1.5, "min": 0.5, "max": 5,
                   "label": "Stop (×ATR)"},
        "tp_atr": {"type": "float", "default": 3.0, "min": 1, "max": 10,
                   "label": "Objectif (×ATR)"},
    }

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        df = ctx.df
        if (df is None or df.empty or ctx.timeframe not in ("", "1d")
                or not {"High", "Low", "Close"}.issubset(df.columns)):
            return []
        index = df.index
        if (not isinstance(index, pd.DatetimeIndex) or index.hasnans
                or not index.is_monotonic_increasing
                or index.normalize().has_duplicates):
            return []
        prices = df[["High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce")
        if (not np.isfinite(prices.to_numpy()).all()
                or (prices <= 0).any().any()
                or (prices.High < prices.Low).any()
                or (prices.Close > prices.High).any()
                or (prices.Close < prices.Low).any()):
            return []
        sl_mult = float(ctx.params.get("sl_atr", 1.5))
        tp_mult = float(ctx.params.get("tp_atr", 3.0))
        if not np.isfinite([sl_mult, tp_mult]).all() or min(sl_mult, tp_mult) <= 0:
            return []

        window = pd.Timedelta(weeks=52)
        highs = prices.High.rolling(window, closed="left", min_periods=200).max()
        lows = prices.Low.rolling(window, closed="left", min_periods=200).min()
        volatility = atr(prices, 14)
        signals = []
        for i in range(1, len(prices)):
            if index[i] - index[0] < window:
                continue
            high, low = highs.iat[i], lows.iat[i]
            entry, previous = prices.Close.iat[i], prices.Close.iat[i - 1]
            a = volatility.iat[i]
            if not np.isfinite([high, low, a]).all() or a <= 0:
                continue
            if previous <= high < entry:
                side, direction, level = Side.LONG, 1, high
            elif previous >= low > entry:
                side, direction, level = Side.SHORT, -1, low
            else:
                continue
            stop = entry - direction * sl_mult * a
            target = entry + direction * tp_mult * a
            if min(stop, target) <= 0:
                continue
            signals.append(Signal(
                time=index[i], side=side, entry=float(entry), sl=float(stop),
                tp1=float(target), setup_type="ANNUAL_HIGH_BREAKOUT" if direction == 1
                else "ANNUAL_LOW_BREAKOUT",
                reason=[f"Clôture au-delà de l'extrême des 52 semaines : {level:g}"],
                meta={"rr": tp_mult / sl_mult, "atr": float(a),
                      "annual_high": float(high), "annual_low": float(low),
                      "lookback_weeks": 52},
            ))
        return signals
