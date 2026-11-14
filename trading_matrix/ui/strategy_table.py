from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.config import PALETTE
from strategies.base import Signal as TradeSignal


class SignalTable(QWidget):
    signalActivated = Signal(object)  # TradeSignal
    aiAnalysisRequested = Signal(object)  # TradeSignal

    COLUMNS = (
        "Heure",
        "Sens",
        "Statut",
        "Setup",
        "Entrée",
        "SL",
        "TP1",
        "TP2",
        "R:R",
        "Conf.",
        "Raisons",
        "IA",
    )
    COL_SIDE = 1
    COL_STATUS = 2
    COL_CONFIDENCE = 9
    COL_REASON = 10
    COL_AI = 11

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
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_REASON, QHeaderView.ResizeMode.Stretch)
        # Les widgets de cellule ne suivent pas le tri : on les replace après tri.
        header.sortIndicatorChanged.connect(self._schedule_ai_refresh)

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
            pending = bool(sig.meta.get("pending"))

            values = [
                sig.time.strftime("%Y-%m-%d %H:%M"),
                sig.side.value,
                "En attente" if pending else "Confirmé",
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
                if col == 0:
                    # Référence stable : l'item se déplace avec le tri.
                    item.setData(Qt.ItemDataRole.UserRole, sig)
                if col == self.COL_STATUS:
                    item.setForeground(
                        QColor(PALETTE["pending"] if pending else PALETTE["text_sub"])
                    )
                    if pending:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        item.setToolTip(
                            "Setup conditionnel : il ne se déclenche que si le prix "
                            "revient dans la zone puis produit une bougie de réaction."
                        )
                elif col in (self.COL_SIDE, self.COL_CONFIDENCE):
                    item.setForeground(color)
                if col == self.COL_SIDE:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)
        self._refresh_ai_buttons()

    def _schedule_ai_refresh(self, *_args) -> None:
        """Le tri est appliqué après l'émission du signal : on diffère la mise à jour."""
        QTimer.singleShot(0, self._refresh_ai_buttons)

    def _refresh_ai_buttons(self, *_args) -> None:
        """Recrée un bouton IA par ligne (appelé après création et après tri)."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            sig = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if sig is None:
                continue

            button = QPushButton("Analyser IA")
            button.setObjectName("aiButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(
                "Analyser ce signal avec un modèle Ollama local.\n"
                "Ollama doit être installé et démarré."
            )
            button.clicked.connect(
                lambda _checked=False, signal=sig: self.aiAnalysisRequested.emit(signal)
            )
            self.table.setCellWidget(row, self.COL_AI, button)

    def clear(self) -> None:
        self.signals = []
        self.table.setRowCount(0)

    def _on_double_click(self, row: int, _col: int) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        sig = item.data(Qt.ItemDataRole.UserRole)
        if sig is None:
            # Ancien comportement de secours (ne devrait plus arriver).
            timestamp = item.text()
            for candidate in self.signals:
                if candidate.time.strftime("%Y-%m-%d %H:%M") == timestamp:
                    sig = candidate
                    break
        if sig is not None:
            self.signalActivated.emit(sig)
