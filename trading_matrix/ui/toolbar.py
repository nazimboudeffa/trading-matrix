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

from trading_matrix.core.config import DEFAULT_INTERVAL, DEFAULT_PERIOD, DEFAULT_SYMBOL, INTERVALS, PERIODS
from trading_matrix.ui.symbol_completer import SymbolCompleter


class Toolbar(QWidget):
    loadRequested = Signal(str, str, str)  # symbol, interval, period
    providerChanged = Signal(str)
    marketsRequested = Signal()  # ouverture de la fenêtre « Marchés »

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.btn_markets = QPushButton("Marchés")
        self.btn_markets.setObjectName("marketsButton")
        self.btn_markets.setToolTip("Ouvrir la liste des marchés (indices et forex)")
        self.btn_markets.clicked.connect(lambda: self.marketsRequested.emit())
        layout.addWidget(self.btn_markets)

        layout.addWidget(QLabel("Symbole"))
        self.symbol_input = QLineEdit(DEFAULT_SYMBOL)
        self.symbol_input.setPlaceholderText("Ex: AAPL, MSFT, BTC-USD")
        self.symbol_input.setFixedWidth(140)
        self.symbol_input.returnPressed.connect(self._emit_load)
        self.symbol_completer = SymbolCompleter(self.symbol_input, self)
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

    def request_load(self, symbol: str) -> None:
        """Renseigne le symbole puis demande le chargement (panneaux externes)."""
        self.symbol_input.setText(symbol.strip().upper())
        self._emit_load()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
