"""Exemple de stratégie personnalisée : croisement EMA rapide/lente avec filtre ATR.

Ce fichier montre comment :
- déclarer `id`, `name`, `description`, `params_schema`
- hériter de `BaseStrategy`
- retourner des `Signal` compatibles avec le moteur et l'UI
"""

from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy, Side, Signal, StrategyContext
from strategies.utils import atr


class EmaCrossATR(BaseStrategy):
    id = "user_ema_cross_atr"
    name = "EMA Cross + ATR (exemple perso)"
    description = (
        "Croisement EMA rapide/lente avec stop basé sur l'ATR. "
        "Exemple pédagogique de stratégie utilisateur."
    )
    params_schema = {
        "fast": {"type": "int", "default": 12, "min": 2, "max": 100, "label": "EMA rapide"},
        "slow": {"type": "int", "default": 26, "min": 3, "max": 300, "label": "EMA lente"},
        "atr_mult": {"type": "float", "default": 1.5, "min": 0.2, "max": 5.0, "label": "Multiplicateur ATR"},
        "rr": {"type": "float", "default": 2.0, "min": 1.0, "max": 6.0, "label": "R:R cible"},
        "min_confidence": {"type": "int", "default": 55, "min": 0, "max": 100, "label": "Confiance min."},
    }

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        df = ctx.df
        fast = int(ctx.params.get("fast", 12))
        slow = int(ctx.params.get("slow", 26))
        atr_mult = float(ctx.params.get("atr_mult", 1.5))
        rr_target = float(ctx.params.get("rr", 2.0))
        min_conf = int(ctx.params.get("min_confidence", 55))

        if len(df) < slow + 5:
            return []

        ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
        atr_series = atr(df, 14)

        signals: list[Signal] = []
        for i in range(slow + 2, len(df)):
            prev_fast, prev_slow = ema_fast.iloc[i - 1], ema_slow.iloc[i - 1]
            cur_fast, cur_slow = ema_fast.iloc[i], ema_slow.iloc[i]
            a = atr_series.iloc[i]
            if not pd.notna(a) or a <= 0:
                continue

            cross_up = prev_fast <= prev_slow and cur_fast > cur_slow
            cross_down = prev_fast >= prev_slow and cur_fast < cur_slow
            if not (cross_up or cross_down):
                continue

            close = float(df["Close"].iloc[i])
            if cross_up:
                sl = close - atr_mult * float(a)
                risk = close - sl
                tp1 = close + rr_target * risk
                tp2 = close + (rr_target + 1.0) * risk
                side = Side.LONG
                conf = min_conf
            else:
                sl = close + atr_mult * float(a)
                risk = sl - close
                tp1 = close - rr_target * risk
                tp2 = close - (rr_target + 1.0) * risk
                side = Side.SHORT
                conf = min_conf

            # Bonus simple : pente de l'EMA lente dans le sens du signal
            slope = ema_slow.iloc[i] - ema_slow.iloc[i - 3]
            if (cross_up and slope > 0) or (cross_down and slope < 0):
                conf = min(100, conf + 10)

            if conf < min_conf:
                continue

            signals.append(
                Signal(
                    time=df.index[i],
                    side=side,
                    entry=close,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                    confidence=conf,
                    setup_type="EMA_CROSS_ATR",
                    reason=[f"Croisement EMA {fast}/{slow}", f"ATR x{atr_mult}"],
                    meta={"rr": round(rr_target, 2)},
                )
            )

        return signals
