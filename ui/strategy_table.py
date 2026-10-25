from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.config import PALETTE
from strategies.base import Signal as TradeSignal


class SignalTable(QWidget):
    signalActivated = Signal(object)  # TradeSignal

    COLUMNS = ["Heure", "Sens", "Setup", "Entrée", "SL", "TP1", "TP2", "R:R", "Conf.", "Raisons"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals: list[TradeSignal] = []
        self._build_ui()

    def _build_ui(self) -> None:
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, len(self.COLUMNS), self)
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

    def set_signals(self, signals: list[TradeSignal]) -> None:
        self.signals = list(signals)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(signals))

        for row, sig in enumerate(signals):
            is_long = sig.side.value == "LONG"
            color = QColor(PALETTE["up"] if is_long else PALETTE["down"])
            rr = sig.meta.get("rr", "-")

            values = [
                sig.time.strftime("%Y-%m-%d %H:%M"),
                sig.side.value,
                sig.setup_type,
                f"{sig.entry:.2f}",
                f"{sig.sl:.2f}",
                f"{sig.tp1:.2f}",
                f"{sig.tp2:.2f}" if sig.tp2 is not None else "-",
                f"{rr}",
                f"{sig.confidence}%",
                " | ".join(sig.reason),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in (1, 8):
                    item.setForeground(color)
                if col == 1:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)

    def clear(self) -> None:
        self.signals = []
        self.table.setRowCount(0)

    def _on_double_click(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self.signals):
            return
        # row index may shift due to sorting: use the item stored on the row
        item = self.table.item(row, 0)
        if item is None:
            return
        timestamp = item.text()
        for sig in self.signals:
            if sig.time.strftime("%Y-%m-%d %H:%M") == timestamp:
                self.signalActivated.emit(sig)
                return
