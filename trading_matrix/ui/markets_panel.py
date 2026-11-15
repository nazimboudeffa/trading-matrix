"""Panneau « Marchés » : liste des constituants d'un indice ou des paires forex.

Le chargement (cache disque ou Wikipédia) s'exécute dans un thread séparé pour
ne jamais bloquer l'interface. Un double-clic sur une ligne — ou le bouton
« Sélectionner » — demande le chargement du graphique via le signal
``instrumentActivated``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import (
    QObject,
    QSortFilterProxyModel,
    QThread,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from trading_matrix.data.markets import (
    MarketSnapshot,
    fetch_market,
    list_markets,
)

logger = logging.getLogger(__name__)

_COLUMNS = ("Symbole", "Nom", "Secteur", "Place")
_SOURCE_LABELS = {
    "network": "Réseau",
    "cache": "Cache",
    "seeds": "Hors ligne",
    "static": "Intégré",
}


class _MarketThread(QThread):
    """Charge un marché hors du thread UI."""

    loaded = Signal(int, object)  # generation, MarketSnapshot
    failed = Signal(int, str)

    def __init__(self, market_id: str, force: bool, generation: int, parent: QObject | None = None):
        super().__init__(parent)
        self._market_id = market_id
        self._force = force
        self._generation = generation

    def run(self) -> None:
        try:
            snapshot = fetch_market(self._market_id, force=self._force)
        except Exception as exc:  # noqa: BLE001 - message affiché dans le panneau
            self.failed.emit(self._generation, str(exc))
            return
        self.loaded.emit(self._generation, snapshot)


def _format_age(updated_at: datetime | None) -> str:
    if updated_at is None:
        return ""
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - updated_at
    if delta < timedelta(minutes=1):
        return "à l'instant"
    if delta < timedelta(hours=1):
        return f"il y a {int(delta.total_seconds() // 60)} min"
    if delta < timedelta(days=1):
        return f"il y a {int(delta.total_seconds() // 3600)} h"
    return f"il y a {delta.days} j"


class MarketsPanel(QWidget):
    """Combo de marchés, filtre local, tableau triable et actions de chargement."""

    instrumentActivated = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._generation = 0
        self._threads: set[_MarketThread] = set()
        self._snapshot: MarketSnapshot | None = None
        self._build_ui()
        QTimer.singleShot(0, self.reload)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.market_combo = QComboBox()
        previous_category: str | None = None
        for market in list_markets():
            if previous_category is not None and market.category != previous_category:
                # Séparateur entre les groupes (Indices / Forex).
                self.market_combo.insertSeparator(self.market_combo.count())
            self.market_combo.addItem(market.label, market.id)
            previous_category = market.category
        self.market_combo.currentIndexChanged.connect(lambda _index: self.reload())
        header.addWidget(self.market_combo, 1)

        self.refresh_button = QPushButton("Actualiser")
        self.refresh_button.setToolTip("Forcer la récupération depuis Wikipédia")
        self.refresh_button.clicked.connect(lambda: self.reload(force=True))
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrer par symbole, nom, secteur…")
        self.filter_input.setClearButtonEnabled(True)
        layout.addWidget(self.filter_input)

        self.model = QStandardItemModel(0, len(_COLUMNS), self)
        self.model.setHorizontalHeaderLabels(list(_COLUMNS))

        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)  # filtre sur toutes les colonnes
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.table = QTableView()
        self.table.setObjectName("marketTable")
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 90)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.status_label = QLabel("Chargement…")
        self.status_label.setObjectName("marketStatus")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("marketCount")
        footer.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignRight)

        self.select_button = QPushButton("Sélectionner")
        self.select_button.setObjectName("primaryButton")
        self.select_button.setToolTip("Charger l'actif sélectionné dans le graphique")
        self.select_button.setEnabled(False)
        self.select_button.clicked.connect(self._on_select)
        footer.addWidget(self.select_button, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(footer)

        self.filter_input.textChanged.connect(self._apply_filter)

        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------ Chargement
    def reload(self, force: bool = False) -> None:
        """(Re)charge le marché sélectionné ; ``force`` ignore le cache frais."""
        market_id = self.market_combo.currentData()
        if not market_id:
            return
        self._generation += 1
        generation = self._generation
        self.status_label.setText("Chargement…")
        self.refresh_button.setEnabled(False)

        thread = _MarketThread(str(market_id), force, generation, self)
        thread.loaded.connect(self._on_loaded)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(lambda t=thread: self._forget_thread(t))
        self._threads.add(thread)
        thread.start()

    def _on_loaded(self, generation: int, snapshot: object) -> None:
        if generation != self._generation or not isinstance(snapshot, MarketSnapshot):
            return
        self._snapshot = snapshot
        self._populate(snapshot)
        self._update_status(snapshot)
        self.refresh_button.setEnabled(True)

    def _on_failed(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        logger.warning("Marchés indisponibles : %s", message)
        self.model.removeRows(0, self.model.rowCount())
        self._snapshot = None
        self.status_label.setText(f"Indisponible : {message}")
        self.count_label.setText("")
        self.refresh_button.setEnabled(True)

    def _populate(self, snapshot: MarketSnapshot) -> None:
        self.model.removeRows(0, self.model.rowCount())
        for instrument in snapshot.instruments:
            symbol_item = QStandardItem(instrument.symbol)
            symbol_item.setData(instrument.symbol, Qt.ItemDataRole.UserRole)
            name_item = QStandardItem(instrument.name)
            sector_item = QStandardItem(instrument.sector)
            place_item = QStandardItem(instrument.exchange or snapshot.market.label)
            for item in (symbol_item, name_item, sector_item, place_item):
                item.setEditable(False)
            if instrument.name:
                symbol_item.setToolTip(f"{instrument.symbol} — {instrument.name}")
            self.model.appendRow([symbol_item, name_item, sector_item, place_item])
        self._update_count()

    def _update_status(self, snapshot: MarketSnapshot) -> None:
        source = _SOURCE_LABELS.get(snapshot.source, snapshot.source)
        age = _format_age(snapshot.updated_at)
        parts = [source, f"{len(snapshot.instruments)} titres"]
        if age:
            parts.append(age)
        self.status_label.setText(" · ".join(parts))

    def _apply_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text.strip())
        self._update_count()

    def _update_count(self) -> None:
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        if not total:
            self.count_label.setText("")
        elif shown == total:
            self.count_label.setText(f"{total} titres")
        else:
            self.count_label.setText(f"{shown} / {total}")

    # ------------------------------------------------------------------ Actions
    def _symbol_at(self, index) -> str:
        """Symbole porté par une ligne du proxy (vide si aucune)."""
        if index is None or not index.isValid():
            return ""
        source_index = self.proxy.mapToSource(index)
        item = self.model.item(source_index.row(), 0)
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or item.text()).strip()

    def _on_double_click(self, index) -> None:
        symbol = self._symbol_at(index)
        if symbol:
            self.instrumentActivated.emit(symbol)

    def _on_select(self) -> None:
        """Charge l'actif sélectionné (bouton « Sélectionner »)."""
        symbol = self._symbol_at(self.table.currentIndex())
        if symbol:
            self.instrumentActivated.emit(symbol)

    def _on_selection_changed(self, *_) -> None:
        model = self.table.selectionModel()
        self.select_button.setEnabled(bool(model and model.hasSelection()))

    def _forget_thread(self, thread: _MarketThread) -> None:
        self._threads.discard(thread)
        thread.deleteLater()

    def shutdown(self) -> None:
        """Arrête les chargements en cours (fermeture de l'app)."""
        for thread in list(self._threads):
            try:
                thread.requestInterruption()
            except RuntimeError:
                pass
        for thread in list(self._threads):
            try:
                thread.wait(1500)
            except RuntimeError:
                pass
        self._threads.clear()
