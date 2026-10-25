from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


@dataclass
class PlotItem:
    label: str
    series: pd.Series
    color: str = "#d1d4dc"
    width: int = 2
    style: str = "solid"  # solid/dash


@dataclass
class IndicatorResult:
    name: str
    kind: Literal["overlay", "subplot"] = "overlay"
    plots: list[PlotItem] = field(default_factory=list)
    height: int = 120
    hlines: list[tuple[float, str]] = field(default_factory=list)
    vlines: list[tuple[float, str]] = field(default_factory=list)
