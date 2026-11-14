from __future__ import annotations

from typing import Any

import pandas as pd

from strategies.base import Side, Signal, StrategyContext
from strategies.registry import StrategyRegistry


class StrategyEngine:
    """Exécute une stratégie et filtre les signaux selon des critères d'affichage."""

    def __init__(self, registry: StrategyRegistry | None = None):
        self.registry = registry or StrategyRegistry()

    def run(
        self,
        strategy_id: str,
        df: pd.DataFrame,
        *,
        symbol: str = "",
        timeframe: str = "",
        params: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[Signal]:
        entry = self.registry.get(strategy_id)
        if entry is None:
            raise KeyError(f"Stratégie inconnue: {strategy_id}")

        merged = self.registry.default_params(strategy_id)
        if params:
            merged.update(params)

        ctx = StrategyContext(df=df, symbol=symbol, timeframe=timeframe, params=merged)
        signals = entry.instance.analyze(ctx) or []

        filters = filters or {}
        signals = self._filter(signals, filters)
        signals.sort(key=lambda s: s.time)
        return signals

    @staticmethod
    def _filter(signals: list[Signal], filters: dict[str, Any]) -> list[Signal]:
        min_conf = filters.get("min_confidence")
        min_rr = filters.get("min_rr")
        side_filter = filters.get("side")  # "LONG" | "SHORT" | None
        max_signals = filters.get("max_signals")

        out: list[Signal] = []
        for s in signals:
            if min_conf is not None and s.confidence < min_conf:
                continue
            rr = s.meta.get("rr")
            if min_rr is not None and rr is not None and rr < min_rr:
                continue
            if side_filter in ("LONG", "SHORT") and s.side.value != side_filter:
                continue
            out.append(s)

        if max_signals:
            out = out[-int(max_signals):]
        return out
