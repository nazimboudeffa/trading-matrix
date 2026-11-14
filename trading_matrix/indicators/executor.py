import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd

try:
    import ta
except Exception:
    ta = None


class CustomIndicatorExecutor:
    ALLOWED_BUILTINS = {"len": len, "range": range, "min": min, "max": max, "abs": abs, "round": round, "int": int, "float": float, "bool": bool, "enumerate": enumerate, "zip": zip, "sum": sum, "list": list, "dict": dict, "tuple": tuple, "set": set}

    def __init__(self, root: Path | str = "user_indicators"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load_module(self, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(f"userind_{path.stem}", path)
        if not spec or not spec.loader:
            raise ImportError(f"Impossible de charger {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def execute(self, mod: ModuleType, df: pd.DataFrame, params: dict[str, Any] | None = None):
        params = params or {}
        if not hasattr(mod, "compute"):
            raise AttributeError("Ton indicateur doit définir une fonction compute(df, **params)")
        func = mod.compute
        return func(df, **params)
