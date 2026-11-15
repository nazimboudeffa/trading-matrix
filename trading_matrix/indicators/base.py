from dataclasses import dataclass, field
from typing import Any, Literal

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


@dataclass
class ParamSpec:
    """Description d'un paramètre d'indicateur (génère un widget dans l'UI)."""

    name: str
    type: str = "int"  # "int" | "float" | "bool" | "str"
    default: Any = 0
    min: float | None = None
    max: float | None = None
    step: float | None = None
    label: str = ""


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def normalize_params(params: dict | None) -> list[ParamSpec]:
    """Convertit un dictionnaire ``PARAMS`` en liste de ``ParamSpec``.

    Deux formes sont acceptées pour chaque entrée :

    - une valeur simple : ``{"period": 20}`` (type déduit) ;
    - un dictionnaire de description :
      ``{"period": {"type": "int", "default": 20, "min": 5, "max": 200, "label": "Période"}}``.
    """
    specs: list[ParamSpec] = []
    for key, value in (params or {}).items():
        if isinstance(value, dict):
            default = value.get("default")
            specs.append(
                ParamSpec(
                    name=key,
                    type=value.get("type", _infer_type(default)),
                    default=default,
                    min=value.get("min"),
                    max=value.get("max"),
                    step=value.get("step"),
                    label=value.get("label", key),
                )
            )
        else:
            specs.append(
                ParamSpec(
                    name=key,
                    type=_infer_type(value),
                    default=value,
                    label=key,
                )
            )
    return specs

