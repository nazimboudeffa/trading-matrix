from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from indicators.custom_registry import CustomRegistry
from ui.indicator_editor import IndicatorEditorDialog


class CustomIndicatorPanel(QWidget):
    applyCustom = Signal(str, dict)
    clearCustom = Signal()

    def __init__(self, registry: CustomRegistry | None = None, parent=None):
        super().__init__(parent)
        self.registry = registry or CustomRegistry()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Mes indicateurs")
        title.setStyleSheet("color: #d1d4dc; font-weight: bold; font-size: 11pt;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.desc_label = QLabel("Sélectionne un indicateur")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #787b86;")
        layout.addWidget(self.desc_label)

        btn_new = QPushButton("Nouveau...")
        btn_new.clicked.connect(self.new_indicator)
        layout.addWidget(btn_new)

        btn_refresh = QPushButton("Rafraîchir")
        btn_refresh.clicked.connect(self.refresh)
        layout.addWidget(btn_refresh)

        btn_apply = QPushButton("Appliquer à la vue")
        btn_apply.setObjectName("primaryButton")
        btn_apply.clicked.connect(self.apply_selected)
        layout.addWidget(btn_apply)

        btn_clear = QPushButton("Effacer indicateurs perso")
        btn_clear.clicked.connect(self.clearCustom.emit)
        layout.addWidget(btn_clear)

        self.list_widget.itemSelectionChanged.connect(self.update_desc)

    def refresh(self):
        self.list_widget.clear()
        try:
            self.registry.discover()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))
            return
        for cid, item in self.registry.items.items():
            it = QListWidgetItem(item.name)
            it.setData(256, cid)
            self.list_widget.addItem(it)
        self.desc_label.setText(f"{len(self.registry.items)} indicateur(s) trouvé(s) dans user_indicators/")

    def update_desc(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        cid = items[0].data(256)
        item = self.registry.items.get(cid)
        if item:
            desc = item.description or "Aucune description"
            params = item.params
            self.desc_label.setText(f"{desc}\n\nParamètres: {params}")

    def new_indicator(self):
        dlg = IndicatorEditorDialog(self)
        if dlg.exec():
            self.refresh()

    def apply_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "Info", "Sélectionne un indicateur")
            return
        cid = items[0].data(256)
        item = self.registry.items.get(cid)
        if not item:
            return
        self.applyCustom.emit(cid, dict(item.params))
