from pathlib import Path
from dataclasses import dataclass
from typing import Any

from indicators.executor import CustomIndicatorExecutor
from indicators.base import IndicatorResult, PlotItem


@dataclass
class CustomIndicator:
    id: str
    name: str
    path: Path
    module: Any
    description: str = ""
    params: dict = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}


class CustomRegistry:
    def __init__(self, root: str = "user_indicators"):
        self.root = Path(root)
        self.executor = CustomIndicatorExecutor(self.root)
        self.items: dict[str, CustomIndicator] = {}

    def discover(self):
        self.items.clear()
        for py in self.root.glob("*.py"):
            if py.name.startswith("_"):
                continue
            try:
                mod = self.executor.load_module(py)
                name = getattr(mod, "NAME", py.stem)
                desc = getattr(mod, "DESCRIPTION", "")
                params = getattr(mod, "PARAMS", {}) or {}
                cid = py.stem
                self.items[cid] = CustomIndicator(id=cid, name=name, path=py, module=mod, description=desc, params=params)
            except Exception as e:
                print(f"[custom] Erreur chargement {py.name}: {e}")
        return self.items

    def compute(self, cid: str, df, params: dict | None = None):
        if cid not in self.items:
            raise KeyError(cid)
        item = self.items[cid]
        res = self.executor.execute(item.module, df, params or {})
        if isinstance(res, IndicatorResult):
            return res
        if isinstance(res, dict):
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
            return IndicatorResult(name=res.get("name", item.name), kind=res.get("kind", "overlay"), plots=plots, height=res.get("height", 120), hlines=res.get("hlines", []), vlines=res.get("vlines", []))
        raise TypeError("compute() doit retourner IndicatorResult ou dict")
