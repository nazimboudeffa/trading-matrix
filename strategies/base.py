from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class Side(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass(slots=True)
class Signal:
    time: pd.Timestamp
    side: Side
    entry: float
    sl: float
    tp1: float
    tp2: float | None = None
    confidence: int = 50  # 0-100
    setup_type: str = "price_action"
    reason: list[str] = field(default_factory=list)
    zone_price_low: float | None = None
    zone_price_high: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyContext:
    df: pd.DataFrame
    symbol: str = ""
    timeframe: str = ""
    params: dict[str, Any] = field(default_factory=dict)


class BaseStrategy:
    id: str = "base"
    name: str = "Base Strategy"
    description: str = ""
    params_schema: dict[str, Any] = {}

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        raise NotImplementedError
