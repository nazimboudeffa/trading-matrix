"""Autocomplétion du champ « Symbole » du toolbar.

La recherche réseau (``yfinance``) est exécutée dans un thread séparé, avec un
délai de 300 ms après la dernière frappe. Les résultats s'affichent dans une
petite liste sous le champ : le symbole inséré est toujours le symbole boursier
seul, le nom et la place ne servent qu'à l'affichage.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, QPoint, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
)

from trading_matrix.data.markets import Instrument
from trading_matrix.data.symbol_search import search_symbols

logger = logging.getLogger(__name__)

_DEBOUNCE_MS = 300
_MIN_CHARS = 2
_MAX_RESULTS = 10
_POPUP_MIN_WIDTH = 360


class _SearchThread(QThread):
    """Exécute ``search_symbols`` hors du thread UI."""

    done = Signal(int, object)  # generation, list[Instrument]
    failed = Signal(int, str)

    def __init__(self, query: str, generation: int, parent: QObject | None = None):
        super().__init__(parent)
        self._query = query
        self._generation = generation

    def run(self) -> None:
        try:
            results = search_symbols(self._query, limit=_MAX_RESULTS)
        except Exception as exc:  # noqa: BLE001 - jamais bloquant pour l'UI
            self.failed.emit(self._generation, str(exc))
            return
        self.done.emit(self._generation, results)


class SymbolCompleter(QObject):
    """Suggestions de symboles attachées à un ``QLineEdit``."""

    symbolSelected = Signal(str)

    def __init__(self, line_edit: QLineEdit, parent: QObject | None = None):
        super().__init__(parent or line_edit)
        self._line_edit = line_edit
        self._generation = 0
        self._results: list[Instrument] = []
        self._threads: set[_SearchThread] = set()

        # Liste flottante : fenêtre « Tool » sans focus, pour ne pas voler la
        # frappe au champ de saisie (contrairement à Qt.Popup).
        self._popup = QListWidget(line_edit)
        self._popup.setObjectName("symbolPopup")
        self._popup.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self._popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._popup.setUniformItemSizes(True)
        self._popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._popup.itemClicked.connect(self._on_item_clicked)
        self._popup.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_DEBOUNCE_MS)
        self._timer.timeout.connect(self._start_search)

        self._line_edit.textEdited.connect(self._on_text_edited)
        self._line_edit.installEventFilter(self)
        self._window = self._line_edit.window()
        self._window.installEventFilter(self)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            app.aboutToQuit.connect(self.shutdown)

    # ------------------------------------------------------------------ UI
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self._line_edit:
            if event.type() == QEvent.Type.KeyPress:
                if self._handle_key(event):
                    return True
            elif event.type() == QEvent.Type.Hide:
                self._hide_popup()
            return False

        # La fenêtre principale passe au second plan : on referme.
        if obj is self._window and event.type() == QEvent.Type.WindowDeactivate:
            self._hide_popup()
            return False

        # Clic hors du champ et de la liste : on referme.
        if event.type() == QEvent.Type.MouseButtonPress and self._popup.isVisible():
            if not self._is_popup_event(event):
                self._hide_popup()
        return False

    def _is_popup_event(self, event: QEvent) -> bool:
        position = getattr(event, "globalPosition", None)
        if position is None:
            return False
        point = position().toPoint()
        widget = QApplication.widgetAt(point)
        if widget is None:
            return False
        return widget is self._popup or self._popup.isAncestorOf(widget)

    def _handle_key(self, event) -> bool:
        key = event.key()

        if key == Qt.Key.Key_Escape:
            if self._popup.isVisible():
                self._hide_popup()
                return True
            return False

        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            if not self._popup.isVisible():
                if key == Qt.Key.Key_Down and self._results:
                    self._show_popup()
                    return True
                if key == Qt.Key.Key_Down and len(self._line_edit.text().strip()) >= _MIN_CHARS:
                    self._timer.stop()
                    self._start_search()
                    return True
                return False
            count = self._popup.count()
            if count == 0:
                return False
            row = self._popup.currentRow()
            if key == Qt.Key.Key_Down:
                row = 0 if row < 0 else (row + 1) % count
            else:
                row = count - 1 if row < 0 else (row - 1) % count
            self._popup.setCurrentRow(row)
            return True

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._popup.isVisible() and self._popup.currentItem() is not None:
                self._apply(self._popup.currentItem(), load=True)
                return True
            self._hide_popup()
            return False

        if key == Qt.Key.Key_Tab:
            if self._popup.isVisible() and self._popup.currentItem() is not None:
                self._apply(self._popup.currentItem(), load=False)
                return True

        return False

    # ------------------------------------------------------------------ Recherche
    def _on_text_edited(self, text: str) -> None:
        self._generation += 1
        self._timer.stop()
        self._results = []
        self._hide_popup()
        if len(text.strip()) < _MIN_CHARS:
            return
        self._timer.start()

    def _start_search(self) -> None:
        text = self._line_edit.text().strip()
        if len(text) < _MIN_CHARS:
            return
        generation = self._generation
        thread = _SearchThread(text, generation, self)
        thread.done.connect(self._on_results)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(lambda t=thread: self._forget_thread(t))
        self._threads.add(thread)
        thread.start()

    def _on_results(self, generation: int, results) -> None:
        if generation != self._generation:
            return
        self._results = [item for item in (results or []) if isinstance(item, Instrument)]
        if not self._results:
            self._hide_popup()
            return

        self._popup.clear()
        for instrument in self._results:
            details = instrument.name
            if instrument.exchange:
                details = f"{details} ({instrument.exchange})" if details else f"({instrument.exchange})"
            text = f"{instrument.symbol}   {details}".rstrip()
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, instrument.symbol)
            item.setToolTip(text)
            self._popup.addItem(item)
        self._popup.setCurrentRow(0)
        self._show_popup()

    def _on_failed(self, generation: int, message: str) -> None:
        if generation == self._generation:
            logger.warning("Autocomplétion indisponible : %s", message)
        self._hide_popup()

    def _forget_thread(self, thread: _SearchThread) -> None:
        self._threads.discard(thread)
        thread.deleteLater()

    # ------------------------------------------------------------------ Liste
    def _show_popup(self) -> None:
        if not self._results:
            return

        width = max(self._line_edit.width() + 260, _POPUP_MIN_WIDTH)
        rows = min(self._popup.count(), _MAX_RESULTS)
        height = 6
        for row in range(rows):
            hint = self._popup.sizeHintForRow(row)
            height += max(hint, 26)
        self._popup.setFixedWidth(width)
        self._popup.setFixedHeight(height)

        anchor = self._line_edit.mapToGlobal(QPoint(0, self._line_edit.height() + 2))
        screen = self._line_edit.screen()
        if screen is not None:
            area = screen.availableGeometry()
            x = min(max(anchor.x(), area.left()), area.right() - width)
            y = anchor.y()
            if y + height > area.bottom():
                above = self._line_edit.mapToGlobal(QPoint(0, 0)).y() - height - 2
                y = max(above, area.top())
            anchor = QPoint(x, y)

        self._popup.move(anchor)
        self._popup.show()
        self._popup.raise_()

    def _hide_popup(self) -> None:
        if self._popup.isVisible():
            self._popup.hide()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self._apply(item, load=False)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._apply(item, load=True)

    def _apply(self, item: QListWidgetItem, load: bool) -> None:
        symbol = str(item.data(Qt.ItemDataRole.UserRole) or "").strip().upper()
        if not symbol:
            return

        self._hide_popup()
        self._results = []
        self._generation += 1  # ignore les réponses encore en vol

        self._line_edit.blockSignals(True)
        self._line_edit.setText(symbol)
        self._line_edit.blockSignals(False)
        self._line_edit.setCursorPosition(len(symbol))
        self._line_edit.setFocus(Qt.FocusReason.OtherFocusReason)

        self.symbolSelected.emit(symbol)
        if load:
            self._line_edit.returnPressed.emit()

    # ------------------------------------------------------------------ Arrêt
    def shutdown(self) -> None:
        """Arrête proprement les recherches en cours (fermeture de l'app)."""
        self._timer.stop()
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
        self._popup.hide()
