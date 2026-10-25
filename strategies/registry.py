from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from strategies.base import BaseStrategy


@dataclass
class StrategyEntry:
    id: str
    name: str
    description: str
    instance: BaseStrategy
    source: str = "builtin"  # builtin | user
    path: Path | None = None
    params_schema: dict[str, Any] = field(default_factory=dict)


def _builtin_strategies() -> list[BaseStrategy]:
    from strategies.price_action.general import PriceActionGeneral

    return [PriceActionGeneral()]


def _load_user_module(path: Path) -> ModuleType:
    name = f"userstrat_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ImportError(f"Impossible de charger {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class StrategyRegistry:
    def __init__(self, user_dir: str | Path = "strategies/user_strategies"):
        self.user_dir = Path(user_dir)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.items: dict[str, StrategyEntry] = {}

    def discover(self) -> dict[str, StrategyEntry]:
        self.items.clear()

        for strat in _builtin_strategies():
            self.items[strat.id] = StrategyEntry(
                id=strat.id,
                name=strat.name,
                description=strat.description,
                instance=strat,
                source="builtin",
                params_schema=strat.params_schema,
            )

        for py in sorted(self.user_dir.glob("*.py")):
            if py.name.startswith("_"):
                continue
            try:
                mod = _load_user_module(py)
            except Exception as e:
                print(f"[strategies] Erreur chargement {py.name}: {e}")
                continue

            classes = [
                obj
                for obj in vars(mod).values()
                if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy
            ]
            for cls in classes:
                try:
                    inst = cls()
                except Exception as e:
                    print(f"[strategies] Erreur instanciation {cls.__name__}: {e}")
                    continue
                self.items[inst.id] = StrategyEntry(
                    id=inst.id,
                    name=inst.name,
                    description=inst.description,
                    instance=inst,
                    source="user",
                    path=py,
                    params_schema=inst.params_schema,
                )

        return self.items

    def get(self, sid: str) -> StrategyEntry | None:
        return self.items.get(sid)

    def default_params(self, sid: str) -> dict[str, Any]:
        entry = self.get(sid)
        if not entry:
            return {}
        return {
            key: spec.get("default")
            for key, spec in (entry.params_schema or {}).items()
            if isinstance(spec, dict)
        }
