from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from strategies.registry import StrategyRegistry


class StrategyPanel(QWidget):
    analyzeRequested = Signal(str, dict, dict)  # strategy_id, params, filters
    clearRequested = Signal()
    refreshRequested = Signal()

    def __init__(self, registry: StrategyRegistry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.param_widgets: dict[str, QWidget] = {}
        self._build_ui()
        self.refresh_strategies()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Stratégies")
        title.setStyleSheet("color: #d1d4dc; font-weight: bold; font-size: 11pt;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Stratégie"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        layout.addWidget(self.strategy_combo)

        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #787b86;")
        layout.addWidget(self.desc_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(10)

        # Paramètres de la stratégie (dynamiques)
        self.params_group = QGroupBox("Paramètres")
        self.params_form = QFormLayout(self.params_group)
        c_layout.addWidget(self.params_group)

        # Filtres d'affichage
        filters_group = QGroupBox("Filtres d'affichage")
        f_layout = QFormLayout(filters_group)

        self.filter_side = QComboBox()
        self.filter_side.addItems(["Toutes", "LONG", "SHORT"])
        f_layout.addRow("Sens", self.filter_side)

        self.filter_min_conf = QSpinBox()
        self.filter_min_conf.setRange(0, 100)
        self.filter_min_conf.setValue(0)
        f_layout.addRow("Confiance min. (%)", self.filter_min_conf)

        self.filter_min_rr = QDoubleSpinBox()
        self.filter_min_rr.setRange(0.0, 10.0)
        self.filter_min_rr.setSingleStep(0.1)
        self.filter_min_rr.setValue(0.0)
        f_layout.addRow("R:R min.", self.filter_min_rr)

        self.filter_max = QSpinBox()
        self.filter_max.setRange(0, 1000)
        self.filter_max.setSpecialValueText("Illimité")
        self.filter_max.setValue(0)
        f_layout.addRow("Max signaux", self.filter_max)

        c_layout.addWidget(filters_group)
        c_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        self.btn_refresh = QPushButton("Rafraîchir stratégies")
        self.btn_refresh.clicked.connect(self.refresh_strategies)
        layout.addWidget(self.btn_refresh)

        self.btn_analyze = QPushButton("Analyser le graphique")
        self.btn_analyze.setObjectName("primaryButton")
        self.btn_analyze.clicked.connect(self._emit_analyze)
        layout.addWidget(self.btn_analyze)

        self.btn_clear = QPushButton("Effacer les signaux")
        self.btn_clear.clicked.connect(self.clearRequested.emit)
        layout.addWidget(self.btn_clear)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: #787b86;")
        layout.addWidget(self.result_label)

    # ------------------------------------------------------------------
    def refresh_strategies(self) -> None:
        current = self.strategy_combo.currentData()
        self.registry.discover()
        self.strategy_combo.blockSignals(True)
        self.strategy_combo.clear()
        for sid, entry in self.registry.items.items():
            self.strategy_combo.addItem(entry.name, sid)
        self.strategy_combo.blockSignals(False)
        if current:
            idx = self.strategy_combo.findData(current)
            if idx >= 0:
                self.strategy_combo.setCurrentIndex(idx)
        self._on_strategy_changed()

    def current_strategy_id(self) -> str | None:
        return self.strategy_combo.currentData()

    # ------------------------------------------------------------------
    def _on_strategy_changed(self, *_args) -> None:
        sid = self.current_strategy_id()
        self._clear_params()

        if not sid:
            self.desc_label.setText("")
            return

        entry = self.registry.get(sid)
        if not entry:
            return

        self.desc_label.setText(entry.description)

        schema = entry.params_schema or {}
        for key, spec in schema.items():
            if not isinstance(spec, dict):
                continue
            widget = self._make_widget(spec)
            label = spec.get("label", key)
            self.params_form.addRow(label, widget)
            self.param_widgets[key] = widget

    def _clear_params(self) -> None:
        self.param_widgets.clear()
        while self.params_form.rowCount() > 0:
            self.params_form.removeRow(0)

    def _make_widget(self, spec: dict) -> QWidget:
        t = spec.get("type", "int")
        default = spec.get("default")

        if t == "bool":
            w = QCheckBox()
            w.setChecked(bool(default))
            return w
        if t == "float":
            w = QDoubleSpinBox()
            w.setRange(float(spec.get("min", -1e9)), float(spec.get("max", 1e9)))
            w.setSingleStep(float(spec.get("step", 0.1)))
            w.setValue(float(default if default is not None else 0.0))
            return w
        if t == "str":
            from PySide6.QtWidgets import QLineEdit

            w = QLineEdit(str(default or ""))
            return w

        w = QSpinBox()
        w.setRange(int(spec.get("min", -10**6)), int(spec.get("max", 10**6)))
        w.setValue(int(default if default is not None else 0))
        return w

    def collect_params(self) -> dict:
        params = {}
        for key, widget in self.param_widgets.items():
            if isinstance(widget, QCheckBox):
                params[key] = widget.isChecked()
            elif isinstance(widget, QDoubleSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QSpinBox):
                params[key] = widget.value()
            elif hasattr(widget, "text"):
                params[key] = widget.text()
        return params

    def collect_filters(self) -> dict:
        side = self.filter_side.currentText()
        return {
            "side": None if side == "Toutes" else side,
            "min_confidence": self.filter_min_conf.value(),
            "min_rr": self.filter_min_rr.value(),
            "max_signals": self.filter_max.value() or None,
        }

    def _emit_analyze(self) -> None:
        sid = self.current_strategy_id()
        if not sid:
            return
        self.analyzeRequested.emit(sid, self.collect_params(), self.collect_filters())

    def set_result(self, count: int) -> None:
        self.result_label.setText(f"{count} signal(aux) détecté(s)")
