"""Price Action général : structure de marché + Order Blocks non mitigés.

Principes (alignés sur SmaCrossover) :

* paramètres lus de façon défensive à partir de ``params_schema`` (une seule
  source de vérité pour types, bornes et valeurs par défaut) ;
* aucun seuil codé en dur : buffers de SL, tolérance de zone et période ATR
  sont des paramètres ;
* logique LONG/SHORT factorisée (un seul code, un signe de direction) ;
* pas de lookahead : la structure est recalculée sur l'historique tronqué.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trading_matrix.strategies.base import BaseStrategy, Side, Signal, StrategyContext
from trading_matrix.strategies.price_action.patterns import detect_reaction
from trading_matrix.strategies.price_action.structure import find_swings, get_trend
from trading_matrix.strategies.price_action.zones import Zone, find_order_blocks
from trading_matrix.strategies.utils import atr

# Zone.index est la bougie de l'OB ; la suivante est l'impulsion qui le
# confirme. Seules les bougies postérieures peuvent donc consommer la zone
# (décalage de 2), aussi bien pour l'historique que pour les setups à venir.
_CONSUME_OFFSET = 2
_PENDING_CONF_CAP = 70


@dataclass(frozen=True)
class _SideInfo:
    side: Side
    sign: int          # +1 long, -1 short
    ob_kind: str       # type de zone recherchée
    trend: str         # structure alignée avec le signal
    adverse: str       # structure contraire
    react: str         # "haussière" / "baissière"
    ob: str            # "haussier" / "baissier"
    tag: str           # "BULL" / "BEAR"


_SIDES = {
    Side.LONG: _SideInfo(Side.LONG, 1, "OB_BULL", "BULLISH", "BEARISH", "haussière", "haussier", "BULL"),
    Side.SHORT: _SideInfo(Side.SHORT, -1, "OB_BEAR", "BEARISH", "BULLISH", "baissière", "baissier", "BEAR"),
}


@dataclass(frozen=True)
class _Settings:
    left: int
    right: int
    lookback: int
    min_rr: float
    min_conf: int
    require_trend: bool
    cooldown: int
    show_pending: bool
    pending_max: int
    max_distance_atr: float
    atr_period: int
    sl_buffer_atr: float
    zone_tol_atr: float
    recompute_every: int
    allow_sweep: bool


class PriceActionGeneral(BaseStrategy):
    """Stratégie générale basée sur la structure de marché et les Order Blocks."""

    id = "pa_general"
    name = "Price Action Général"
    display_order = 30
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
            "type": "float", "default": 4.0, "min": 0.0, "max": 20.0, "label": "Distance max (×ATR)",
        },
        # --- nouveaux paramètres (anciennement codés en dur) ---
        "atr_period": {"type": "int", "default": 14, "min": 5, "max": 50, "label": "Période ATR"},
        "sl_buffer_atr": {
            "type": "float", "default": 0.25, "min": 0.0, "max": 2.0, "label": "Marge du stop (×ATR)",
        },
        "zone_tolerance_atr": {
            "type": "float", "default": 0.5, "min": 0.0, "max": 2.0, "label": "Tolérance de zone (×ATR)",
        },
        "recompute_every": {
            "type": "int", "default": 5, "min": 1, "max": 50, "label": "Recalcul structure (bougies)",
        },
        "allow_zone_sweep": {
            "type": "bool", "default": False, "label": "Accepter les mèches au-delà de la zone",
        },
    }

    # ------------------------------------------------------------------
    # Paramètres
    # ------------------------------------------------------------------
    def _param(self, p: dict, key: str):
        """Lit un paramètre selon le schéma : cast, valeur par défaut, bornes."""
        spec = self.params_schema[key]
        kind = spec["type"]
        raw = p.get(key, spec["default"])
        if kind == "bool":
            return bool(raw)
        cast = int if kind == "int" else float
        try:
            val = cast(raw)
            if not np.isfinite(val):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            val = cast(spec["default"])
        return cast(max(spec["min"], min(spec["max"], val)))

    def _settings(self, p: dict) -> _Settings:
        g = lambda key: self._param(p, key)  # noqa: E731
        return _Settings(
            left=g("swing_left"),
            right=g("swing_right"),
            lookback=g("lookback_zones"),
            min_rr=g("min_rr"),
            min_conf=g("min_confidence"),
            require_trend=g("require_trend"),
            cooldown=g("cooldown"),
            show_pending=g("show_pending"),
            pending_max=g("pending_max"),
            max_distance_atr=g("pending_max_distance_atr"),
            atr_period=g("atr_period"),
            sl_buffer_atr=g("sl_buffer_atr"),
            zone_tol_atr=g("zone_tolerance_atr"),
            recompute_every=g("recompute_every"),
            allow_sweep=g("allow_zone_sweep"),
        )

    # ------------------------------------------------------------------
    # Analyse principale
    # ------------------------------------------------------------------
    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        df = ctx.df
        if df is None or df.empty or not {"High", "Low", "Close"}.issubset(df.columns):
            return []

        cfg = self._settings(ctx.params or {})
        n = len(df)
        if n < max(cfg.left + cfg.right + 5, 30):
            return []

        # Tableaux numpy extraits une seule fois : évite df.iloc[i] dans la boucle.
        highs = pd.to_numeric(df["High"], errors="coerce").to_numpy(dtype=float)
        lows = pd.to_numeric(df["Low"], errors="coerce").to_numpy(dtype=float)
        closes = pd.to_numeric(df["Close"], errors="coerce").to_numpy(dtype=float)
        atr_arr = np.asarray(atr(df, cfg.atr_period), dtype=float)

        warmup = max(cfg.left + cfg.right + 5, 20)
        signals: list[Signal] = []
        swings: list = []
        trend = "RANGE"
        zones: list[Zone] = []
        last_idx = -10**9
        used_zones: set[tuple[float, float]] = set()

        for i in range(warmup, n):
            # --- Structure : recalcul périodique sur l'historique tronqué (pas de lookahead)
            # Recalcul aussi si aucune zone n'est fraîche : sans cela, une
            # vieille zone encore présente masque un OB apparu entre deux
            # cycles, et le signal sur les bougies récentes est perdu.
            has_fresh_zone = any(z.index >= i - cfg.recompute_every for z in zones)
            if (i - warmup) % cfg.recompute_every == 0 or not has_fresh_zone:
                sub = df.iloc[: i + 1]
                swings = find_swings(sub, cfg.left, cfg.right)
                trend = get_trend(swings)
                zones = [
                    z for z in find_order_blocks(sub, cfg.lookback)
                    if not self._consumed(z, lows, highs, z.index + _CONSUME_OFFSET, i)
                ]
            else:
                # Entre deux recalculs, on retire les zones touchées par la bougie i-1.
                # (L'ancienne version ne filtrait la mitigation qu'au recalcul.)
                zones = [
                    z for z in zones
                    if not self._consumed(
                        z, lows, highs, max(z.index + _CONSUME_OFFSET, i - 1), i
                    )
                ]

            a = atr_arr[i]
            if not np.isfinite(a) or a <= 0 or i - last_idx < cfg.cooldown:
                continue

            reaction = detect_reaction(df, i)
            if not (reaction["bull"] or reaction["bear"]):
                continue

            for info in self._eligible_sides(reaction, trend, cfg.require_trend):
                setup = self._try_setup(
                    info=info, i=i, index=df.index, closes=closes, highs=highs, lows=lows,
                    zones=zones, swings=swings, trend=trend, atr_val=float(a),
                    reaction=reaction, cfg=cfg, used_zones=used_zones,
                )
                if setup is None:
                    continue
                sig, zone_key = setup
                if sig.confidence < cfg.min_conf or sig.meta["rr"] < cfg.min_rr:
                    continue

                signals.append(sig)
                used_zones.add(zone_key)
                last_idx = i
                break

        if cfg.show_pending and cfg.pending_max > 0:
            # État final (sans lookahead) pour les setups conditionnels à venir.
            final_swings = find_swings(df, cfg.left, cfg.right)
            signals.extend(
                self._pending_setups(
                    df=df, lows=lows, highs=highs, closes=closes,
                    zones=find_order_blocks(df, cfg.lookback),
                    swings=final_swings, trend=get_trend(final_swings),
                    atr_val=float(atr_arr[-1]), cfg=cfg, used_zones=used_zones,
                )
            )

        return signals

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _zone_key(zone: Zone) -> tuple[float, float]:
        return (round(zone.bottom, 6), round(zone.top, 6))

    @staticmethod
    def _consumed(zone: Zone, lows: np.ndarray, highs: np.ndarray, start: int, end: int) -> bool:
        """Vrai si le prix a touché ou traversé (gap compris) la zone sur [start, end)."""
        if end <= start:
            return False
        return bool(lows[start:end].min() <= zone.top and highs[start:end].max() >= zone.bottom)

    @staticmethod
    def _eligible_sides(reaction: dict, trend: str, require_trend: bool) -> list[_SideInfo]:
        sides = []
        for side, key in ((Side.LONG, "bull"), (Side.SHORT, "bear")):
            info = _SIDES[side]
            if reaction[key] and not (require_trend and trend == info.adverse):
                sides.append(info)
        return sides

    @staticmethod
    def _targets(swings, i: int, entry: float, risk: float, sign: int) -> list[float]:
        """TP1/TP2/TP3 : prochains swings dans le sens du trade, sinon multiples de R.

        Garantit des objectifs strictement croissants (l'ancienne version
        pouvait produire un TP2 inférieur au TP1 quand TP1 était un swing lointain).
        """
        kind = "HIGH" if sign > 0 else "LOW"
        dists = sorted(
            sign * (s.price - entry)
            for s in swings
            if s.kind == kind and s.index < i and sign * (s.price - entry) > 0
        )
        targets: list[float] = []
        prev = 0.0
        for k in range(3):
            nxt = next((d for d in dists if d > prev), None)
            if nxt is None:
                nxt = max((k + 2) * risk, prev + risk)  # 2R, 3R, 4R au minimum
            targets.append(entry + sign * nxt)
            prev = nxt
        return targets

    # ------------------------------------------------------------------
    # Signaux déclenchés
    # ------------------------------------------------------------------
    def _try_setup(
        self,
        *,
        info: _SideInfo,
        i: int,
        index,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        zones: list[Zone],
        swings,
        trend: str,
        atr_val: float,
        reaction: dict,
        cfg: _Settings,
        used_zones: set[tuple[float, float]],
    ):
        sign = info.sign
        close, low, high = float(closes[i]), float(lows[i]), float(highs[i])
        tol = cfg.zone_tol_atr * atr_val
        buf = cfg.sl_buffer_atr * atr_val

        candidates = []
        for z in zones:
            # Les zones déjà utilisées sont exclues AVANT le choix de la plus
            # récente (avant : on choisissait puis on rejetait, sans essayer les autres).
            if z.kind != info.ob_kind or self._zone_key(z) in used_zones:
                continue
            if sign > 0:
                in_zone = z.bottom <= low <= z.top + tol
                swept = low < z.bottom and close > z.bottom
            else:
                in_zone = z.bottom - tol <= high <= z.top
                swept = high > z.top and close < z.top
            if in_zone or (cfg.allow_sweep and swept):
                candidates.append(z)
        if not candidates:
            return None

        zone = max(candidates, key=lambda z: z.index)
        sl = (min(zone.bottom, low) if sign > 0 else max(zone.top, high)) - sign * buf
        risk = sign * (close - sl)
        if risk <= 0:
            return None

        tp1, tp2, tp3 = self._targets(swings, i, close, risk, sign)
        rr = sign * (tp1 - close) / risk

        conf = 40
        reasons = [f"Réaction {info.react}"]
        if trend == info.trend:
            conf += 20
            reasons.append(f"Structure {info.react}")
        elif trend == "RANGE":
            conf += 5
            reasons.append("Range")
        conf += 15
        reasons.append(f"OB {info.ob} ({zone.bottom:.2f}-{zone.top:.2f})")
        types = list(reaction.get("types", []))
        conf += min(10, 3 * len(types))
        reasons.append("PA: " + ", ".join(types))
        if rr >= 1.5:
            conf += 10
            reasons.append("R:R >= 1.5")

        sig = Signal(
            time=index[i],
            side=info.side,
            entry=close,
            sl=float(sl),
            tp1=float(tp1),
            tp2=float(tp2),
            tp3=float(tp3),
            confidence=int(min(100, conf)),
            setup_type=f"OB_REACTION_{info.tag}",
            reason=reasons,
            zone_price_low=zone.bottom,
            zone_price_high=zone.top,
        )
        sig.meta["rr"] = round(rr, 2)
        sig.meta["atr"] = round(atr_val, 4)
        return sig, self._zone_key(zone)

    # ------------------------------------------------------------------
    # Setups conditionnels
    # ------------------------------------------------------------------
    def _pending_setups(
        self,
        *,
        df: pd.DataFrame,
        lows: np.ndarray,
        highs: np.ndarray,
        closes: np.ndarray,
        zones: list[Zone],
        swings,
        trend: str,
        atr_val: float,
        cfg: _Settings,
        used_zones: set[tuple[float, float]],
    ) -> list[Signal]:
        """Plans d'entrée sur des Order Blocks encore non testés.

        Ces signaux ne prédisent pas le futur : ils ne se déclenchent que si le
        prix revient dans la zone et produit une bougie de réaction. Ils sont
        marqués ``meta["pending"] = True``.
        """
        n = len(df)
        if n < 5 or not np.isfinite(atr_val) or atr_val <= 0:
            return []

        close = float(closes[-1])
        buf = cfg.sl_buffer_atr * atr_val
        candidates: list[tuple[float, int, Signal]] = []

        for zone in zones:
            if zone.kind not in ("OB_BULL", "OB_BEAR") or self._zone_key(zone) in used_zones:
                continue
            # La dernière bougie peut être en train de tester la zone : seules
            # les bougies précédentes comptent comme "consommation".
            if self._consumed(zone, lows, highs, zone.index + _CONSUME_OFFSET, n - 1):
                continue

            info = _SIDES[Side.LONG if zone.kind == "OB_BULL" else Side.SHORT]
            sign = info.sign
            if cfg.require_trend and trend == info.adverse:
                continue

            # Position du prix par rapport à la zone
            if sign > 0:
                if close < zone.bottom:
                    continue
                inside = close <= zone.top
                entry = close if inside else zone.top
            else:
                if close > zone.top:
                    continue
                inside = close >= zone.bottom
                entry = close if inside else zone.bottom

            distance = abs(close - entry)
            if cfg.max_distance_atr > 0 and distance > cfg.max_distance_atr * atr_val:
                continue

            sl = (zone.bottom - buf) if sign > 0 else (zone.top + buf)
            risk = sign * (entry - sl)
            if risk <= 0:
                continue
            tp1, tp2, tp3 = self._targets(swings, n - 1, entry, risk, sign)
            rr = sign * (tp1 - entry) / risk

            last_touch = bool(lows[-1] <= zone.top and highs[-1] >= zone.bottom)
            if not last_touch:
                zone_label = "non testé"
            elif zone.bottom <= close <= zone.top:
                zone_label = "en cours de test"
            else:
                zone_label = "testé sur la dernière bougie"

            conf = 50
            reasons = [
                "Setup conditionnel — non déclenché",
                f"Order Block {info.ob} {zone_label} ({zone.bottom:.2f}–{zone.top:.2f})",
            ]
            if trend == info.trend:
                conf += 10
                reasons.append(f"Structure {'haussière' if sign > 0 else 'baissière'}")
            elif trend == "RANGE":
                conf += 3
                reasons.append("Range")
            else:
                reasons.append(f"Structure {'baissière' if sign > 0 else 'haussière'} (contre-tendance)")
            if inside:
                reasons.append("Prix dans la zone : réaction à confirmer")
            else:
                conf += 2
                dist_pct = distance / close * 100 if close else 0.0
                reasons.append(f"Entrée limite à {entry:.2f} — distance {dist_pct:.1f} %")
            if rr >= 1.5:
                conf += 5
                reasons.append("R:R >= 1.5")
            conf = max(0, min(_PENDING_CONF_CAP, conf))

            if conf < cfg.min_conf or rr < cfg.min_rr:
                continue

            distance_pct = round(distance / close * 100, 2) if close else 0.0
            sig = Signal(
                time=df.index[-1],
                side=info.side,
                entry=float(entry),
                sl=float(sl),
                tp1=float(tp1),
                tp2=float(tp2),
                tp3=float(tp3),
                confidence=conf,
                setup_type=f"OB_PENDING_{info.tag}",
                reason=reasons,
                zone_price_low=zone.bottom,
                zone_price_high=zone.top,
            )
            sig.meta.update(
                {
                    "rr": round(rr, 2),
                    "atr": round(atr_val, 4),
                    "pending": True,
                    "pending_kind": "test" if inside else "approche",
                    "entry_mode": "confirmation" if inside else "limite",
                    "condition": (
                        f"Attendre une bougie de réaction {info.react} (engulfing ou pinbar) "
                        f"dans la zone {zone.bottom:.2f}–{zone.top:.2f}"
                    ),
                    "distance_pct": distance_pct,
                }
            )
            candidates.append((distance_pct, -conf, sig))

        candidates.sort(key=lambda item: (item[0], item[1]))
        return [sig for _, _, sig in candidates[: cfg.pending_max]]