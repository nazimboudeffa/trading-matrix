from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trading_matrix.core.config import USER_INDICATORS_DIR
from trading_matrix.indicators.base import (
    IndicatorResult,
    ParamSpec,
    PlotItem,
    normalize_params,
)
from trading_matrix.indicators.loader import IndicatorLoader


@dataclass
class IndicatorEntry:
    """Indicateur découvert dans ``user_indicators/``."""

    id: str
    name: str
    path: Path
    module: Any
    description: str = ""
    specs: list[ParamSpec] = field(default_factory=list)

    @property
    def defaults(self) -> dict[str, Any]:
        return {spec.name: spec.default for spec in self.specs}


class IndicatorRegistry:
    """Registre des indicateurs (tous définis dans ``user_indicators/``)."""

    def __init__(self, root: str | Path = USER_INDICATORS_DIR):
        self.root = Path(root)
        self.loader = IndicatorLoader(self.root)
        self.items: dict[str, IndicatorEntry] = {}

    def discover(self) -> dict[str, IndicatorEntry]:
        self.items.clear()
        for py in sorted(self.root.glob("*.py")):
            if py.name.startswith("_"):
                continue
            try:
                mod = self.loader.load_module(py)
                specs = normalize_params(getattr(mod, "PARAMS", {}) or {})
                cid = py.stem
                self.items[cid] = IndicatorEntry(
                    id=cid,
                    name=getattr(mod, "NAME", py.stem),
                    path=py,
                    module=mod,
                    description=getattr(mod, "DESCRIPTION", ""),
                    specs=specs,
                )
            except Exception as e:
                print(f"[indicators] Erreur chargement {py.name}: {e}")
        return self.items

    def get(self, cid: str) -> IndicatorEntry | None:
        return self.items.get(cid)

    def compute(self, cid: str, df, params: dict | None = None) -> IndicatorResult:
        entry = self.items.get(cid)
        if entry is None:
            raise KeyError(cid)
        res = self.loader.execute(entry.module, df, params or {})
        if isinstance(res, IndicatorResult):
            return res
        if isinstance(res, dict):
            return self._result_from_dict(res, entry)
        raise TypeError("compute() doit retourner IndicatorResult ou dict")

    @staticmethod
    def _result_from_dict(res: dict, entry: IndicatorEntry) -> IndicatorResult:
        plots = []
        for p in res.get("plots", []):
            if isinstance(p, PlotItem):
                plots.append(p)
                continue
            if len(p) == 4:
                plots.append(PlotItem(label=p[0], series=p[1], color=p[2], width=p[3]))
            elif len(p) == 3:
                plots.append(PlotItem(label=p[0], series=p[1], color=p[2]))
            else:
                plots.append(PlotItem(label=str(p[0]), series=p[1]))
        return IndicatorResult(
            name=res.get("name", entry.name),
            kind=res.get("kind", "overlay"),
            plots=plots,
            height=res.get("height", 120),
            hlines=res.get("hlines", []),
            vlines=res.get("vlines", []),
        )
