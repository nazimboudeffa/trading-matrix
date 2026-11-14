from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from core.config import DEFAULT_INTERVAL, DEFAULT_PERIOD, DEFAULT_SYMBOL, INTERVALS, PERIODS


class Toolbar(QWidget):
    loadRequested = Signal(str, str, str)  # symbol, interval, period
    providerChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Symbole"))
        self.symbol_input = QLineEdit(DEFAULT_SYMBOL)
        self.symbol_input.setPlaceholderText("Ex: AAPL, MSFT, BTC-USD")
        self.symbol_input.setFixedWidth(140)
        self.symbol_input.returnPressed.connect(self._emit_load)
        layout.addWidget(self.symbol_input)

        layout.addWidget(QLabel("Intervalle"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(INTERVALS)
        self.interval_combo.setCurrentText(DEFAULT_INTERVAL)
        layout.addWidget(self.interval_combo)

        layout.addWidget(QLabel("Période"))
        self.period_combo = QComboBox()
        self.period_combo.addItems(PERIODS)
        self.period_combo.setCurrentText(DEFAULT_PERIOD)
        layout.addWidget(self.period_combo)

        self.btn_load = QPushButton("Charger")
        self.btn_load.setObjectName("primaryButton")
        self.btn_load.clicked.connect(self._emit_load)
        layout.addWidget(self.btn_load)

        layout.addStretch(1)

        self.status_label = QLabel("Prêt")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

    def _emit_load(self) -> None:
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            return
        self.loadRequested.emit(
            symbol,
            self.interval_combo.currentText(),
            self.period_combo.currentText(),
        )

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
