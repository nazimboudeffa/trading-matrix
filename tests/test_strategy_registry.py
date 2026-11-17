"""Tests de l'ordre d'affichage des stratégies."""

from __future__ import annotations

from pathlib import Path

from trading_matrix.strategies.registry import StrategyRegistry


def _write_strategy(path: Path, class_name: str, sid: str, name: str, order: int) -> None:
    path.write_text(
        "from trading_matrix.strategies.base import BaseStrategy\n"
        f"class {class_name}(BaseStrategy):\n"
        f"    id = {sid!r}\n"
        f"    name = {name!r}\n"
        f"    display_order = {order}\n",
        encoding="utf-8",
    )


def test_ordered_items_follows_display_order(tmp_path: Path) -> None:
    # Noms de fichiers volontairement dans un ordre alphabétique différent.
    _write_strategy(tmp_path / "z_price.py", "Price", "pa_general", "Price Action", 30)
    _write_strategy(tmp_path / "a_ema.py", "Ema", "ema_cross", "EMA", 20)
    _write_strategy(tmp_path / "b_sma.py", "Sma", "sma_crossover", "SMA", 10)

    registry = StrategyRegistry(user_dir=tmp_path)
    registry.discover()

    assert [entry.id for entry in registry.ordered_items()] == [
        "sma_crossover",
        "ema_cross",
        "pa_general",
    ]
