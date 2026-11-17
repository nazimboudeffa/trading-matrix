"""La liste des signaux émet le signal cliqué dès le premier clic."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PySide6.QtWidgets import QApplication

from trading_matrix.strategies.base import Side, Signal
from trading_matrix.ui.strategy_table import SignalTable

_APP = QApplication.instance() or QApplication([])


def _signal() -> Signal:
    return Signal(
        time=pd.Timestamp("2024-01-01 12:00"),
        side=Side.LONG,
        entry=100.0,
        sl=99.0,
        tp1=102.0,
        confidence=60,
        setup_type="OB_REACTION_BULL",
    )


def test_single_click_activates_signal() -> None:
    table = SignalTable()
    sig = _signal()
    table.set_signals([sig])

    received: list[Signal] = []
    table.signalActivated.connect(received.append)

    table._on_cell_clicked(0, 0)

    assert received == [sig]
