"""Croisement de moyennes mobiles simples (SMA) avec gestion ATR.

La stratégie reste volontairement générique :

* aucun symbole ni niveau de prix n'est codé en dur ;
* tous les seuils dépendent de l'ATR (volatilité de l'actif) et non d'une
  valeur absolue, ce qui la rend utilisable sur actions, indices, forex ou
  crypto ;
* l'analyse parcourt tout l'historique fourni, et non uniquement la dernière
  bougie, afin d'afficher tous les croisements passés sur le graphique ;
* un cooldown évite d'enchaîner des signaux contradictoires trop proches.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_matrix.strategies.base import BaseStrategy, Side, Signal, StrategyContext
from trading_matrix.strategies.utils import atr


class SmaCrossover(BaseStrategy):
    id = "sma_crossover"
    name = "SMA 20/50 Crossover"
    description = (
        "Croisement de moyennes mobiles avec SL/TP basés sur l'ATR. "
        "Analyse tout l'historique, score de confiance adaptatif et "
        "cooldown pour éviter les signaux redondants."
    )

    params_schema = {
        "fast_period": {
            "type": "int", "default": 20, "min": 2, "max": 100,
            "label": "SMA rapide",
        },
        "slow_period": {
            "type": "int", "default": 50, "min": 5, "max": 300,
            "label": "SMA lente",
        },
        "atr_period": {
            "type": "int", "default": 14, "min": 5, "max": 50,
            "label": "Période ATR",
        },
        "sl_atr": {
            "type": "float", "default": 1.5, "min": 0.5, "max": 5,
            "label": "Stop (×ATR)",
        },
        "tp_atr": {
            "type": "float", "default": 3.0, "min": 1, "max": 10,
            "label": "TP1 (×ATR)",
        },
        "slope_lookback": {
            "type": "int", "default": 5, "min": 1, "max": 50,
            "label": "Fenêtre de pente",
        },
        "cooldown": {
            "type": "int", "default": 5, "min": 0, "max": 50,
            "label": "Cooldown (bougies)",
        },
        "trend_filter": {
            "type": "bool", "default": False,
            "label": "Filtre de tendance",
        },
    }

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        df = ctx.df
        if df is None or df.empty or not {"High", "Low", "Close"}.issubset(df.columns):
            return []

        p = ctx.params or {}

        fast = max(2, int(p.get("fast_period", 20)))
        slow = max(fast + 1, int(p.get("slow_period", 50)))
        atr_period = max(2, int(p.get("atr_period", 14)))
        sl_mult = max(0.1, float(p.get("sl_atr", 1.5)))
        tp_mult = max(0.1, float(p.get("tp_atr", 3.0)))
        slope_lookback = max(1, int(p.get("slope_lookback", 5)))
        cooldown = max(0, int(p.get("cooldown", 5)))
        trend_filter = bool(p.get("trend_filter", False))

        # Il faut assez de bougies pour la SMA lente, l'ATR et la pente.
        warmup = max(slow, atr_period - 1, slow - 1 + slope_lookback)
        if len(df) <= warmup:
            return []

        close = pd.to_numeric(df["Close"], errors="coerce")

        sma_fast = close.rolling(fast, min_periods=fast).mean()
        sma_slow = close.rolling(slow, min_periods=slow).mean()
        atr_values = atr(df, atr_period)

        # Pente des SMA exprimée en unités d'ATR : comparable d'un actif à
        # l'autre (forex, action, crypto), contrairement à une pente brute.
        fast_slope = (sma_fast - sma_fast.shift(slope_lookback)) / atr_values
        slow_slope = (sma_slow - sma_slow.shift(slope_lookback)) / atr_values

        # Régime de volatilité relatif à l'ATR médian récent.
        atr_median = atr_values.rolling(50, min_periods=max(5, atr_period)).median()
        vol_ratio = atr_values / atr_median.replace(0, np.nan)

        prev_diff = (sma_fast - sma_slow).shift(1)
        curr_diff = sma_fast - sma_slow

        cross_up = (prev_diff <= 0) & (curr_diff > 0)
        cross_down = (prev_diff >= 0) & (curr_diff < 0)

        signals: list[Signal] = []
        last_signal_idx = -10**9

        for i in np.flatnonzero((cross_up | cross_down).to_numpy()):
            i = int(i)
            if i < warmup:
                continue

            # Cooldown : pas de nouveau signal tant que le précédent est trop
            # récent, même si un croisement opposé se produit.
            if i - last_signal_idx <= cooldown:
                continue

            a = atr_values.iat[i]
            entry = close.iat[i]
            if not np.isfinite(a) or a <= 0 or not np.isfinite(entry) or entry <= 0:
                continue

            is_long = bool(cross_up.iat[i])
            side = Side.LONG if is_long else Side.SHORT

            fs = fast_slope.iat[i]
            ss = slow_slope.iat[i]
            vr = vol_ratio.iat[i]

            # Filtre optionnel : ne trader que dans le sens de la pente de la
            # SMA lente. Désactivé par défaut pour rester polyvalent.
            if trend_filter and np.isfinite(ss) and (
                (is_long and ss <= 0) or (not is_long and ss >= 0)
            ):
                continue

            # ----- Score de confiance (facteurs génériques, sans seuil de prix)
            confidence = 50
            reasons = [
                f"Croisement SMA {fast}/{slow} {'haussier' if is_long else 'baissier'}"
            ]

            if np.isfinite(fs):
                if (is_long and fs > 0) or (not is_long and fs < 0):
                    confidence += 10
                    reasons.append("SMA rapide orientée dans le sens du signal")
                elif (is_long and fs < 0) or (not is_long and fs > 0):
                    confidence -= 10
                    reasons.append("SMA rapide encore contre le signal")

            if np.isfinite(ss) and (
                (is_long and ss > 0) or (not is_long and ss < 0)
            ):
                confidence += 10
                reasons.append("SMA lente orientée dans le sens du signal")

            sma_s = sma_slow.iat[i]
            if np.isfinite(sma_s) and (
                (is_long and entry > sma_s) or (not is_long and entry < sma_s)
            ):
                confidence += 5
                reasons.append("Clôture du bon côté de la SMA lente")

            # Bougie de confirmation (corps dans le sens du signal).
            open_i = df["Open"].iat[i] if "Open" in df.columns else np.nan
            if np.isfinite(open_i) and (
                (is_long and entry > open_i) or (not is_long and entry < open_i)
            ):
                confidence += 5
                reasons.append("Bougie de confirmation")

            # Volatilité normale par rapport à son propre historique récent.
            if np.isfinite(vr):
                if 0.4 <= vr <= 2.5:
                    confidence += 5
                    reasons.append("Volatilité dans sa norme récente")
                elif vr > 4:
                    confidence -= 10
                    reasons.append("Volatilité exceptionnellement élevée")

            confidence = int(max(0, min(100, confidence)))

            # ----- Stop et objectifs, tous exprimés en multiples d'ATR.
            risk = sl_mult * float(a)
            if is_long:
                sl = entry - risk
                tp1 = entry + tp_mult * float(a)
                tp2 = tp1 + risk
                tp3 = tp2 + risk
            else:
                sl = entry + risk
                tp1 = entry - tp_mult * float(a)
                tp2 = tp1 - risk
                tp3 = tp2 - risk

            rr = abs(tp1 - entry) / risk if risk > 0 else 0.0
            reasons.append(f"Stop {sl_mult:g}×ATR, TP1 {tp_mult:g}×ATR (R:R {rr:.2f})")

            signals.append(Signal(
                time=df.index[i],
                side=side,
                entry=float(entry),
                sl=float(sl),
                tp1=float(tp1),
                tp2=float(tp2),
                tp3=float(tp3),
                confidence=confidence,
                setup_type=(
                    "SMA_BULLISH_CROSS" if is_long else "SMA_BEARISH_CROSS"
                ),
                reason=reasons,
                meta={
                    "rr": round(rr, 2),
                    "atr": float(a),
                    "atr_pct": float(a / entry * 100),
                    "sma_fast": float(sma_fast.iat[i]),
                    "sma_slow": float(sma_s),
                    "slope_fast_atr": float(fs) if np.isfinite(fs) else None,
                    "slope_slow_atr": float(ss) if np.isfinite(ss) else None,
                    "symbol": ctx.symbol,
                    "timeframe": ctx.timeframe,
                },
            ))
            last_signal_idx = i

        return signals
