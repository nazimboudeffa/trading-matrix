from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from trading_matrix.core.config import PALETTE
from trading_matrix.indicators.base import ParamSpec
from trading_matrix.indicators.registry import IndicatorRegistry
from trading_matrix.ui.indicator_editor import IndicatorEditorDialog


class IndicatorPanel(QWidget):
    """Panneau unique listant tous les indicateurs de ``user_indicators/``.

    Chaque indicateur est présenté dans un groupe cochable ; ses paramètres
    (décrits par ``PARAMS`` dans le fichier de l'indicateur) génèrent
    automatiquement les widgets correspondants.
    """

    indicatorsChanged = Signal(list)  # liste de (id, params) cochés
    clearRequested = Signal()

    def __init__(self, registry: IndicatorRegistry | None = None, parent=None):
        super().__init__(parent)
        self.registry = registry or IndicatorRegistry()
        self._widgets: dict[str, tuple[QGroupBox, dict[str, QWidget]]] = {}
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Indicateurs")
        title.setStyleSheet(f"color: {PALETTE['text']}; font-weight: bold; font-size: 11pt;")
        layout.addWidget(title)

        hint = QLabel("Tous les indicateurs vivent dans le dossier user_indicators/.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {PALETTE['text_sub']};")
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        btn_apply = QPushButton("Appliquer")
        btn_apply.setObjectName("primaryButton")
        btn_apply.clicked.connect(self._emit)
        layout.addWidget(btn_apply)

        btn_clear = QPushButton("Effacer tout")
        btn_clear.clicked.connect(self.clearRequested.emit)
        layout.addWidget(btn_clear)

        row = QHBoxLayout()
        btn_refresh = QPushButton("Rafraîchir")
        btn_refresh.clicked.connect(self.refresh)
        row.addWidget(btn_refresh)
        btn_new = QPushButton("Nouveau...")
        btn_new.clicked.connect(self.new_indicator)
        row.addWidget(btn_new)
        layout.addLayout(row)

        btn_folder = QPushButton("Ouvrir le dossier")
        btn_folder.clicked.connect(self.open_folder)
        layout.addWidget(btn_folder)

    # ------------------------------------------------------------------ Données
    def refresh(self) -> None:
        # Vide les groupes existants.
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._widgets.clear()

        try:
            self.registry.discover()
        except Exception as e:
            self.registry.items.clear()
            label = QLabel(f"Erreur de chargement des indicateurs : {e}")
            label.setWordWrap(True)
            self.list_layout.insertWidget(0, label)
            return

        if not self.registry.items:
            label = QLabel("Aucun indicateur trouvé dans user_indicators/.")
            label.setWordWrap(True)
            self.list_layout.insertWidget(0, label)
            return

        for cid, entry in self.registry.items.items():
            self.list_layout.insertWidget(self.list_layout.count() - 1, self._build_group(cid, entry))

    def _build_group(self, cid: str, entry) -> QGroupBox:
        box = QGroupBox(entry.name)
        box.setCheckable(True)
        box.setChecked(False)
        if entry.description:
            box.setToolTip(entry.description)
        v = QVBoxLayout(box)
        v.setSpacing(6)

        if entry.description:
            desc = QLabel(entry.description)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {PALETTE['text_sub']};")
            v.addWidget(desc)

        param_widgets: dict[str, QWidget] = {}
        for spec in entry.specs:
            row = QHBoxLayout()
            row.addWidget(QLabel(spec.label or spec.name))
            widget = self._make_widget(spec)
            param_widgets[spec.name] = widget
            row.addWidget(widget, 1)
            v.addLayout(row)

        self._widgets[cid] = (box, param_widgets)
        return box

    @staticmethod
    def _make_widget(spec: ParamSpec) -> QWidget:
        if spec.type == "bool":
            w = QCheckBox()
            w.setChecked(bool(spec.default))
            return w
        if spec.type == "float":
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(float(spec.min if spec.min is not None else -1e9), float(spec.max if spec.max is not None else 1e9))
            if spec.step:
                w.setSingleStep(float(spec.step))
            w.setValue(float(spec.default or 0.0))
            return w
        if spec.type == "int":
            w = QSpinBox()
            w.setRange(int(spec.min if spec.min is not None else -1_000_000), int(spec.max if spec.max is not None else 1_000_000))
            if spec.step:
                w.setSingleStep(int(spec.step))
            w.setValue(int(spec.default or 0))
            return w
        w = QLineEdit(str(spec.default if spec.default is not None else ""))
        return w

    @staticmethod
    def _read_widget(spec: ParamSpec, widget: QWidget):
        if spec.type == "bool":
            return widget.isChecked()
        if spec.type == "float":
            return widget.value()
        if spec.type == "int":
            return widget.value()
        return widget.text()

    # ------------------------------------------------------------------ Actions
    def _emit(self) -> None:
        selection: list[tuple[str, dict]] = []
        for cid, (box, param_widgets) in self._widgets.items():
            if not box.isChecked():
                continue
            entry = self.registry.items.get(cid)
            if entry is None:
                continue
            params = {
                spec.name: self._read_widget(spec, param_widgets[spec.name])
                for spec in entry.specs
                if spec.name in param_widgets
            }
            selection.append((cid, params))
        self.indicatorsChanged.emit(selection)

    def new_indicator(self) -> None:
        dlg = IndicatorEditorDialog(self)
        if dlg.exec():
            self.refresh()

    def open_folder(self) -> None:
        path = self.registry.root.resolve()
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            try:
                subprocess.Popen(["explorer", str(path)])
            except Exception:
                pass
