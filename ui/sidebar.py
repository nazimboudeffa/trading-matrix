from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import PALETTE


class IndicatorPanel(QWidget):
    indicatorsChanged = Signal(dict)
    clearRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Indicateurs")
        title.setStyleSheet(f"color: {PALETTE['text']}; font-weight: bold; font-size: 11pt;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(10)

        # SMA
        sma_group = QGroupBox("SMA")
        sma_layout = QVBoxLayout(sma_group)
        self.sma_check = QCheckBox("Activer")
        sma_layout.addWidget(self.sma_check)
        row = QVBoxLayout()
        row.addWidget(QLabel("Période"))
        self.sma_period = QSpinBox()
        self.sma_period.setRange(5, 200)
        self.sma_period.setValue(20)
        row.addWidget(self.sma_period)
        sma_layout.addLayout(row)
        c_layout.addWidget(sma_group)

        # EMA
        ema_group = QGroupBox("EMA")
        ema_layout = QVBoxLayout(ema_group)
        self.ema_check = QCheckBox("Activer")
        ema_layout.addWidget(self.ema_check)
        row2 = QVBoxLayout()
        row2.addWidget(QLabel("Période"))
        self.ema_period = QSpinBox()
        self.ema_period.setRange(5, 200)
        self.ema_period.setValue(50)
        row2.addWidget(self.ema_period)
        ema_layout.addLayout(row2)
        c_layout.addWidget(ema_group)

        # Bollinger Bands
        bb_group = QGroupBox("Bandes de Bollinger")
        bb_layout = QVBoxLayout(bb_group)
        self.bb_check = QCheckBox("Activer")
        bb_layout.addWidget(self.bb_check)
        bb_layout.addWidget(QLabel("Période"))
        self.bb_period = QSpinBox()
        self.bb_period.setRange(10, 100)
        self.bb_period.setValue(20)
        bb_layout.addWidget(self.bb_period)
        bb_layout.addWidget(QLabel("Écart-type"))
        self.bb_std = QDoubleSpinBox()
        self.bb_std.setRange(1.0, 3.0)
        self.bb_std.setSingleStep(0.5)
        self.bb_std.setValue(2.0)
        bb_layout.addWidget(self.bb_std)
        c_layout.addWidget(bb_group)

        # RSI
        rsi_group = QGroupBox("RSI (sous-graphique)")
        rsi_layout = QVBoxLayout(rsi_group)
        self.rsi_check = QCheckBox("Activer")
        rsi_layout.addWidget(self.rsi_check)
        rsi_layout.addWidget(QLabel("Période"))
        self.rsi_period = QSpinBox()
        self.rsi_period.setRange(7, 30)
        self.rsi_period.setValue(14)
        rsi_layout.addWidget(self.rsi_period)
        c_layout.addWidget(rsi_group)

        # MACD
        macd_group = QGroupBox("MACD (sous-graphique)")
        macd_layout = QVBoxLayout(macd_group)
        self.macd_check = QCheckBox("Activer")
        macd_layout.addWidget(self.macd_check)
        macd_layout.addWidget(QLabel("Fast"))
        self.macd_fast = QSpinBox()
        self.macd_fast.setRange(5, 50)
        self.macd_fast.setValue(12)
        macd_layout.addWidget(self.macd_fast)
        macd_layout.addWidget(QLabel("Slow"))
        self.macd_slow = QSpinBox()
        self.macd_slow.setRange(10, 100)
        self.macd_slow.setValue(26)
        macd_layout.addWidget(self.macd_slow)
        macd_layout.addWidget(QLabel("Signal"))
        self.macd_signal = QSpinBox()
        self.macd_signal.setRange(5, 30)
        self.macd_signal.setValue(9)
        macd_layout.addWidget(self.macd_signal)
        c_layout.addWidget(macd_group)

        c_layout.addStretch(1)

        btn_apply = QPushButton("Appliquer")
        btn_apply.setObjectName("primaryButton")
        btn_apply.clicked.connect(self._emit)
        c_layout.addWidget(btn_apply)

        btn_clear = QPushButton("Effacer tout")
        btn_clear.clicked.connect(self.clearRequested.emit)
        c_layout.addWidget(btn_clear)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _emit(self) -> None:
        cfg = {
            "sma": {"enabled": self.sma_check.isChecked(), "period": self.sma_period.value()},
            "ema": {"enabled": self.ema_check.isChecked(), "period": self.ema_period.value()},
            "bb": {"enabled": self.bb_check.isChecked(), "period": self.bb_period.value(), "std": self.bb_std.value()},
            "rsi": {"enabled": self.rsi_check.isChecked(), "period": self.rsi_period.value()},
            "macd": {"enabled": self.macd_check.isChecked(), "fast": self.macd_fast.value(), "slow": self.macd_slow.value(), "signal": self.macd_signal.value()},
        }
        self.indicatorsChanged.emit(cfg)
