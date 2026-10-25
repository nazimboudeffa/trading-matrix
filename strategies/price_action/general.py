from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Side, Signal, StrategyContext
from strategies.price_action.patterns import detect_reaction
from strategies.price_action.structure import find_swings, get_trend
from strategies.price_action.zones import Zone, find_order_blocks
from strategies.utils import atr


class PriceActionGeneral(BaseStrategy):
    """Stratégie générale basée sur la structure de marché et les Order Blocks."""

    id = "pa_general"
    name = "Price Action Général"
    description = (
        "Structure de marché (HH/HL, LH/LL), Order Blocks non mitigés et "
        "confirmation Price Action (engulfing, pinbar). Signaux avec SL/TP et score de confluence."
    )
    params_schema = {
        "swing_left": {"type": "int", "default": 3, "min": 1, "max": 10, "label": "Swings gauche"},
        "swing_right": {"type": "int", "default": 3, "min": 1, "max": 10, "label": "Swings droite"},
        "lookback_zones": {"type": "int", "default": 60, "min": 20, "max": 300, "label": "Lookback zones"},
        "min_rr": {"type": "float", "default": 1.2, "min": 0.5, "max": 5.0, "label": "R:R minimum"},
        "min_confidence": {"type": "int", "default": 50, "min": 0, "max": 100, "label": "Confiance min."},
        "require_trend": {"type": "bool", "default": True, "label": "Tendance requise"},
        "cooldown": {"type": "int", "default": 5, "min": 0, "max": 50, "label": "Cooldown (bougies)"},
    }

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        df = ctx.df
        p = ctx.params
        left = int(p.get("swing_left", 3))
        right = int(p.get("swing_right", 3))
        lookback = int(p.get("lookback_zones", 60))
        min_rr = float(p.get("min_rr", 1.2))
        min_conf = int(p.get("min_confidence", 50))
        require_trend = bool(p.get("require_trend", True))
        cooldown = int(p.get("cooldown", 5))

        n = len(df)
        if n < max(left + right + 5, 30):
            return []

        atr_series = atr(df, 14)
        signals: list[Signal] = []

        warmup = max(left + right + 5, 20)
        swings = []
        trend = "RANGE"
        zones: list[Zone] = []
        last_signal_side: Side | None = None
        last_signal_idx = -10**9
        used_zones: set[int] = set()

        for i in range(warmup, n):
            # Recalcul périodique de la structure (pas de lookahead : on tronque à i)
            if (i - warmup) % 5 == 0 or not zones:
                sub = df.iloc[: i + 1]
                swings = find_swings(sub, left, right)
                trend = get_trend(swings)
                zones = find_order_blocks(sub, lookback)
                # Ne garder que les zones non touchées avant i
                lows_arr = df["Low"].to_numpy(dtype=float)
                highs_arr = df["High"].to_numpy(dtype=float)
                active: list[Zone] = []
                for z in zones:
                    start_j = z.index + 1
                    if start_j >= i:
                        active.append(z)
                        continue
                    if lows_arr[start_j:i].min() <= z.top and highs_arr[start_j:i].max() >= z.bottom:
                        continue
                    active.append(z)
                zones = active

            row = df.iloc[i]
            a = atr_series.iloc[i]
            if not np.isfinite(a) or a <= 0:
                continue

            reaction = detect_reaction(df, i)
            if not (reaction["bull"] or reaction["bear"]):
                continue

            if i - last_signal_idx < cooldown:
                continue

            setup = self._try_setup(
                df=df,
                i=i,
                row=row,
                zones=zones,
                swings=swings,
                trend=trend,
                atr_val=float(a),
                reaction=reaction,
                require_trend=require_trend,
            )
            if setup is None:
                continue

            sig, zone_key = setup
            if zone_key is not None and zone_key in used_zones:
                continue

            if sig.confidence < min_conf:
                continue

            risk = abs(sig.entry - sig.sl)
            if risk <= 0:
                continue
            reward = abs(sig.tp1 - sig.entry)
            rr = reward / risk
            if rr < min_rr:
                continue

            sig.meta["rr"] = round(rr, 2)
            sig.meta["atr"] = round(float(a), 4)
            signals.append(sig)

            last_signal_side = sig.side
            last_signal_idx = i
            if zone_key is not None:
                used_zones.add(zone_key)

        return signals

    # ------------------------------------------------------------------
    def _try_setup(
        self,
        df: pd.DataFrame,
        i: int,
        row: pd.Series,
        zones: list[Zone],
        swings,
        trend: str,
        atr_val: float,
        reaction: dict,
        require_trend: bool,
    ):
        close = float(row["Close"])
        low = float(row["Low"])
        high = float(row["High"])

        # ---------------- LONG
        if reaction["bull"]:
            if require_trend and trend == "BEARISH":
                return None

            bull_zones = [z for z in zones if z.kind == "OB_BULL" and z.bottom <= low <= z.top + atr_val * 0.5]
            if bull_zones:
                zone = max(bull_zones, key=lambda z: z.index)
                sl = min(zone.bottom, low) - 0.25 * atr_val
                tp1 = self._next_swing_high(swings, i, close)
                if tp1 is None:
                    tp1 = close + 2.0 * (close - sl)
                if tp1 <= close:
                    tp1 = close + 2.0 * (close - sl)
                tp2 = self._next_swing_high(swings, i, tp1) or (close + 3.0 * (close - sl))

                conf = 40
                reasons = ["Réaction haussière"]
                if trend == "BULLISH":
                    conf += 20
                    reasons.append("Structure haussière")
                elif trend == "RANGE":
                    conf += 5
                    reasons.append("Range")
                conf += 15
                reasons.append(f"OB haussier ({zone.bottom:.2f}-{zone.top:.2f})")
                conf += min(10, 3 * len(reaction["types"]))
                reasons.append("PA: " + ", ".join(reaction["types"]))
                if (close - sl) > 0 and (tp1 - close) / (close - sl) >= 1.5:
                    conf += 10
                    reasons.append("R:R >= 1.5")

                sig = Signal(
                    time=df.index[i],
                    side=Side.LONG,
                    entry=close,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                    confidence=min(100, conf),
                    setup_type="OB_REACTION_BULL",
                    reason=reasons,
                    zone_price_low=zone.bottom,
                    zone_price_high=zone.top,
                )
                return sig, (round(zone.bottom, 6), round(zone.top, 6))

        # ---------------- SHORT
        if reaction["bear"]:
            if require_trend and trend == "BULLISH":
                return None

            bear_zones = [z for z in zones if z.kind == "OB_BEAR" and z.bottom - atr_val * 0.5 <= high <= z.top]
            if bear_zones:
                zone = max(bear_zones, key=lambda z: z.index)
                sl = max(zone.top, high) + 0.25 * atr_val
                tp1 = self._next_swing_low(swings, i, close)
                if tp1 is None:
                    tp1 = close - 2.0 * (sl - close)
                if tp1 >= close:
                    tp1 = close - 2.0 * (sl - close)
                tp2 = self._next_swing_low(swings, i, tp1) or (close - 3.0 * (sl - close))

                conf = 40
                reasons = ["Réaction baissière"]
                if trend == "BEARISH":
                    conf += 20
                    reasons.append("Structure baissière")
                elif trend == "RANGE":
                    conf += 5
                    reasons.append("Range")
                conf += 15
                reasons.append(f"OB baissier ({zone.bottom:.2f}-{zone.top:.2f})")
                conf += min(10, 3 * len(reaction["types"]))
                reasons.append("PA: " + ", ".join(reaction["types"]))
                if (sl - close) > 0 and (close - tp1) / (sl - close) >= 1.5:
                    conf += 10
                    reasons.append("R:R >= 1.5")

                sig = Signal(
                    time=df.index[i],
                    side=Side.SHORT,
                    entry=close,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                    confidence=min(100, conf),
                    setup_type="OB_REACTION_BEAR",
                    reason=reasons,
                    zone_price_low=zone.bottom,
                    zone_price_high=zone.top,
                )
                return sig, (round(zone.bottom, 6), round(zone.top, 6))

        return None

    @staticmethod
    def _next_swing_high(swings, i: int, above: float):
        highs = [s.price for s in swings if s.kind == "HIGH" and s.index < i and s.price > above]
        return min(highs) if highs else None

    @staticmethod
    def _next_swing_low(swings, i: int, below: float):
        lows = [s.price for s in swings if s.kind == "LOW" and s.index < i and s.price < below]
        return max(lows) if lows else None
