import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd

from trading_matrix.core.config import USER_INDICATORS_DIR


class IndicatorLoader:
    """Charge et exécute les modules d'indicateurs du dossier ``user_indicators/``."""

    def __init__(self, root: Path | str = USER_INDICATORS_DIR):
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
            raise AttributeError("L'indicateur doit définir une fonction compute(df, **params)")
        return mod.compute(df, **params)
