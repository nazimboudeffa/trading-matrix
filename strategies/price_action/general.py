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
        "show_pending": {"type": "bool", "default": True, "label": "Signaux à venir"},
        "pending_max": {"type": "int", "default": 2, "min": 0, "max": 10, "label": "Max signaux à venir"},
        "pending_max_distance_atr": {
            "type": "float",
            "default": 4.0,
            "min": 0.0,
            "max": 20.0,
            "label": "Distance max (×ATR)",
        },
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
        show_pending = bool(p.get("show_pending", True))
        pending_max = int(p.get("pending_max", 2))
        pending_max_distance_atr = float(p.get("pending_max_distance_atr", 4.0))

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

        if show_pending and pending_max > 0:
            # État final (pas de lookahead) pour les setups conditionnels à venir.
            final_swings = find_swings(df, left, right)
            final_trend = get_trend(final_swings)
            final_zones = find_order_blocks(df, lookback)
            final_atr = atr_series.iloc[-1]
            signals.extend(
                self._pending_setups(
                    df=df,
                    zones=final_zones,
                    swings=final_swings,
                    trend=final_trend,
                    atr_val=float(final_atr) if np.isfinite(final_atr) else float("nan"),
                    min_rr=min_rr,
                    min_conf=min_conf,
                    require_trend=require_trend,
                    max_count=pending_max,
                    max_distance_atr=pending_max_distance_atr,
                    used_zones=used_zones,
                )
            )

        return signals

    # ------------------------------------------------------------------
    def _pending_setups(
        self,
        *,
        df: pd.DataFrame,
        zones: list[Zone],
        swings,
        trend: str,
        atr_val: float,
        min_rr: float,
        min_conf: int,
        require_trend: bool,
        max_count: int,
        max_distance_atr: float = 4.0,
        used_zones: set[int] | None = None,
    ) -> list[Signal]:
        """Setups conditionnels sur des Order Blocks encore non testés.

        Ces signaux ne prédisent pas le futur : ils décrivent un plan d'entrée
        qui ne se déclenchera que si le prix revient dans la zone puis produit
        une bougie de réaction. Ils sont marqués ``meta["pending"] = True``.
        """
        n = len(df)
        if n < 5 or max_count <= 0 or not np.isfinite(atr_val) or atr_val <= 0:
            return []

        close = float(df["Close"].iloc[-1])
        lows = df["Low"].to_numpy(dtype=float)
        highs = df["High"].to_numpy(dtype=float)
        blocked = used_zones or set()
        candidates: list[tuple[float, int, Signal]] = []

        for zone in zones:
            if zone.kind not in ("OB_BULL", "OB_BEAR"):
                continue
            if (round(zone.bottom, 6), round(zone.top, 6)) in blocked:
                continue

            # La dernière bougie peut être en train de tester la zone : on ne
            # considère comme "consommées" que les bougies précédentes.
            start = zone.index + 2
            end = n - 1
            if end > start:
                touched = (lows[start:end] <= zone.top) & (highs[start:end] >= zone.bottom)
                if bool(touched.any()):
                    continue

            last_touch = bool(lows[-1] <= zone.top and highs[-1] >= zone.bottom)
            if not last_touch:
                zone_label = "non testé"
            elif zone.bottom <= close <= zone.top:
                zone_label = "en cours de test"
            else:
                zone_label = "testé sur la dernière bougie"

            if zone.kind == "OB_BULL":
                if require_trend and trend == "BEARISH":
                    continue
                if close < zone.bottom:
                    continue
                if close <= zone.top:
                    entry = close
                    entry_mode = "confirmation"
                    pending_kind = "test"
                else:
                    entry = zone.top
                    entry_mode = "limite"
                    pending_kind = "approche"

                if max_distance_atr > 0 and abs(close - entry) > max_distance_atr * atr_val:
                    continue

                sl = zone.bottom - 0.25 * atr_val
                risk = entry - sl
                if risk <= 0:
                    continue
                tp1 = self._next_swing_high(swings, n - 1, entry)
                if tp1 is None or tp1 <= entry:
                    tp1 = entry + 2.0 * risk
                tp2 = self._next_swing_high(swings, n - 1, tp1)
                if tp2 is None or tp2 <= tp1:
                    tp2 = entry + 3.0 * risk
                rr = (tp1 - entry) / risk

                conf = 50
                reasons = [
                    "Setup conditionnel — non déclenché",
                    f"Order Block haussier {zone_label} ({zone.bottom:.2f}–{zone.top:.2f})",
                ]
                if trend == "BULLISH":
                    conf += 10
                    reasons.append("Structure haussière")
                elif trend == "RANGE":
                    conf += 3
                    reasons.append("Range")
                elif not require_trend:
                    reasons.append("Structure baissière (contre-tendance)")
                if pending_kind == "approche":
                    conf += 2
                    dist_pct = abs(close - entry) / close * 100 if close else 0.0
                    reasons.append(
                        f"Entrée limite à {zone.top:.2f} — distance {dist_pct:.1f} %"
                    )
                else:
                    reasons.append("Prix dans la zone : réaction à confirmer")
                if rr >= 1.5:
                    conf += 5
                    reasons.append("R:R >= 1.5")
                conf = max(0, min(70, conf))

                condition = (
                    "Attendre une bougie de réaction haussière (engulfing ou pinbar) "
                    f"dans la zone {zone.bottom:.2f}–{zone.top:.2f}"
                )
                sig = Signal(
                    time=df.index[-1],
                    side=Side.LONG,
                    entry=entry,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                    confidence=conf,
                    setup_type="OB_PENDING_BULL",
                    reason=reasons,
                    zone_price_low=zone.bottom,
                    zone_price_high=zone.top,
                )
            else:
                if require_trend and trend == "BULLISH":
                    continue
                if close > zone.top:
                    continue
                if close >= zone.bottom:
                    entry = close
                    entry_mode = "confirmation"
                    pending_kind = "test"
                else:
                    entry = zone.bottom
                    entry_mode = "limite"
                    pending_kind = "approche"

                if max_distance_atr > 0 and abs(close - entry) > max_distance_atr * atr_val:
                    continue

                sl = zone.top + 0.25 * atr_val
                risk = sl - entry
                if risk <= 0:
                    continue
                tp1 = self._next_swing_low(swings, n - 1, entry)
                if tp1 is None or tp1 >= entry:
                    tp1 = entry - 2.0 * risk
                tp2 = self._next_swing_low(swings, n - 1, tp1)
                if tp2 is None or tp2 >= tp1:
                    tp2 = entry - 3.0 * risk
                rr = (entry - tp1) / risk

                conf = 50
                reasons = [
                    "Setup conditionnel — non déclenché",
                    f"Order Block baissier {zone_label} ({zone.bottom:.2f}–{zone.top:.2f})",
                ]
                if trend == "BEARISH":
                    conf += 10
                    reasons.append("Structure baissière")
                elif trend == "RANGE":
                    conf += 3
                    reasons.append("Range")
                elif not require_trend:
                    reasons.append("Structure haussière (contre-tendance)")
                if pending_kind == "approche":
                    conf += 2
                    dist_pct = abs(close - entry) / close * 100 if close else 0.0
                    reasons.append(
                        f"Entrée limite à {zone.bottom:.2f} — distance {dist_pct:.1f} %"
                    )
                else:
                    reasons.append("Prix dans la zone : réaction à confirmer")
                if rr >= 1.5:
                    conf += 5
                    reasons.append("R:R >= 1.5")
                conf = max(0, min(70, conf))

                condition = (
                    "Attendre une bougie de réaction baissière (engulfing ou pinbar) "
                    f"dans la zone {zone.bottom:.2f}–{zone.top:.2f}"
                )
                sig = Signal(
                    time=df.index[-1],
                    side=Side.SHORT,
                    entry=entry,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                    confidence=conf,
                    setup_type="OB_PENDING_BEAR",
                    reason=reasons,
                    zone_price_low=zone.bottom,
                    zone_price_high=zone.top,
                )

            if conf < min_conf or rr < min_rr:
                continue

            sig.meta.update(
                {
                    "rr": round(rr, 2),
                    "atr": round(float(atr_val), 4),
                    "pending": True,
                    "pending_kind": pending_kind,
                    "entry_mode": entry_mode,
                    "condition": condition,
                    "distance_pct": round(abs(close - entry) / close * 100, 2) if close else 0.0,
                }
            )
            candidates.append((sig.meta["distance_pct"], -conf, sig))

        candidates.sort(key=lambda item: (item[0], item[1]))
        return [sig for _, _, sig in candidates[:max_count]]

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
