"""Fenêtre d'analyse IA d'un signal via Ollama."""

from __future__ import annotations

import threading

from PySide6.QtCore import QSettings, Qt, QThread, QTimer
from PySide6.QtCore import Signal as QtSignal
from PySide6.QtGui import QCloseEvent, QFont, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import ollama_client
from core.signal_context import build_signal_prompt
from strategies.base import Signal as TradeSignal

_SETTINGS_ORG = "TradingMatrix"
_SETTINGS_APP = "TradingMatrix"
_SETTINGS_MODEL_KEY = "ai/model"


def _price(value: float | None) -> str:
    if value is None:
        return "n/d"
    if abs(value) < 1:
        return f"{value:.5f}"
    if abs(value) < 100:
        return f"{value:.3f}"
    return f"{value:.2f}"


class _OllamaWorker(QThread):
    """Exécute la requête Ollama hors du thread UI."""

    chunk = QtSignal(str, str)  # type ("content" | "thinking"), texte
    failed = QtSignal(str)

    def __init__(self, model: str, messages: list[dict[str, str]], parent=None):
        super().__init__(parent)
        self._model = model
        self._messages = messages
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def run(self) -> None:
        try:
            for kind, text in ollama_client.chat_stream(
                self._model, self._messages, stop_event=self._stop
            ):
                if self._stop.is_set():
                    return
                self.chunk.emit(kind, text)
        except Exception as exc:  # noqa: BLE001 - message affiché à l'utilisateur
            if not self._stop.is_set():
                self.failed.emit(str(exc))


class AIAnalysisDialog(QWidget):
    """Fenêtre séparée : contexte du signal, choix du modèle, réponse de l'IA."""

    def __init__(
        self,
        sig: TradeSignal,
        df,
        *,
        symbol: str = "",
        timeframe: str = "",
        strategy_name: str = "",
        strategy_description: str = "",
        status: ollama_client.OllamaStatus | None = None,
        parent=None,
    ):
        super().__init__(parent, Qt.WindowType.Window)

        self.signal = sig
        self.df = df
        self.symbol = symbol or str(sig.meta.get("symbol") or "")
        self.timeframe = timeframe or str(sig.meta.get("timeframe") or "")
        self.strategy_name = strategy_name or str(sig.meta.get("strategy_name") or "")
        self._status = status or ollama_client.get_status()
        self._prompt = build_signal_prompt(
            sig,
            df,
            symbol=self.symbol,
            timeframe=self.timeframe,
            strategy_name=self.strategy_name,
            strategy_description=strategy_description,
        )

        self._worker: _OllamaWorker | None = None
        self._content = ""
        self._thinking = ""
        self._error = ""
        self._stop_requested = False
        self._active_model = ""

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(self._window_title())
        self.resize(1000, 840)
        self._build_ui()
        self._populate_models(self._status)
        self._autostart_timer = QTimer(self)
        self._autostart_timer.setSingleShot(True)
        self._autostart_timer.timeout.connect(self._autostart)
        self._autostart_timer.start(150)

    # ------------------------------------------------------------------ UI
    def _window_title(self) -> str:
        parts = ["Analyse IA"]
        if self.symbol:
            parts.append(self.symbol)
        parts.append(self.signal.side.value)
        if self.timeframe:
            parts.append(self.timeframe)
        return " — ".join(parts)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(self._window_title())
        title.setObjectName("aiTitle")
        title_font = title.font()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        entry = self.signal.entry
        tp2 = " · TP2 " + _price(self.signal.tp2) if self.signal.tp2 is not None else ""
        subtitle = QLabel(
            f"Signal du {self.signal.time:%Y-%m-%d %H:%M} · {self.signal.setup_type} · "
            f"Entrée {_price(entry)} · SL {_price(self.signal.sl)} · "
            f"TP1 {_price(self.signal.tp1)}{tp2} · Confiance {self.signal.confidence} %"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("aiSubtitle")
        layout.addWidget(subtitle)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Modèle Ollama"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(240)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_row.addWidget(self.model_combo, 1)
        self.btn_refresh = QPushButton("Rafraîchir")
        self.btn_refresh.setToolTip("Rescanner les modèles installés dans Ollama")
        self.btn_refresh.clicked.connect(self._refresh_models)
        model_row.addWidget(self.btn_refresh)
        layout.addLayout(model_row)

        self.models_hint = QLabel("")
        self.models_hint.setObjectName("aiHint")
        self.models_hint.setWordWrap(True)
        layout.addWidget(self.models_hint)

        splitter = QSplitter(Qt.Orientation.Vertical, self)

        prompt_group = QGroupBox("Contexte envoyé à l'IA")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_note = QLabel(
            "Texte exact transmis au modèle (aucune donnée postérieure au signal)."
        )
        prompt_note.setObjectName("aiHint")
        prompt_note.setWordWrap(True)
        prompt_layout.addWidget(prompt_note)
        self.prompt_view = QPlainTextEdit()
        self.prompt_view.setReadOnly(True)
        self.prompt_view.setPlainText(self._prompt.display_text())
        self.prompt_view.setFont(self._mono_font(9))
        prompt_layout.addWidget(self.prompt_view)
        splitter.addWidget(prompt_group)

        answer_group = QGroupBox("Analyse de l'IA")
        answer_layout = QVBoxLayout(answer_group)
        self.answer = QTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setPlaceholderText("L'analyse du modèle apparaîtra ici…")
        answer_layout.addWidget(self.answer)
        splitter.addWidget(answer_group)

        self.thinking_group = QGroupBox("Raisonnement du modèle (thinking)")
        thinking_layout = QVBoxLayout(self.thinking_group)
        self.thinking_view = QPlainTextEdit()
        self.thinking_view.setReadOnly(True)
        self.thinking_view.setFont(self._mono_font(9))
        thinking_layout.addWidget(self.thinking_view)
        self.thinking_group.setVisible(False)
        splitter.addWidget(self.thinking_group)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        self.btn_analyze = QPushButton("Analyser avec l'IA")
        self.btn_analyze.setObjectName("primaryButton")
        self.btn_analyze.clicked.connect(self._start_analysis)
        buttons.addWidget(self.btn_analyze)

        self.btn_stop = QPushButton("Arrêter")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_analysis)
        buttons.addWidget(self.btn_stop)

        self.btn_copy = QPushButton("Copier l'analyse")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_analysis)
        buttons.addWidget(self.btn_copy)

        buttons.addStretch(1)
        self.btn_close = QPushButton("Fermer")
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

        self.status_label = QLabel("")
        self.status_label.setObjectName("aiStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    @staticmethod
    def _mono_font(size: int) -> QFont:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(size)
        return font

    # ------------------------------------------------------------- modèles
    def _populate_models(self, status: ollama_client.OllamaStatus) -> None:
        previous = self.model_combo.currentText().strip()
        saved = str(QSettings(_SETTINGS_ORG, _SETTINGS_APP).value(_SETTINGS_MODEL_KEY, ""))

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(status.models)
        for candidate in (previous, saved):
            if candidate and candidate in status.models:
                self.model_combo.setCurrentText(candidate)
                break
        self.model_combo.blockSignals(False)
        self._update_start_button()

        if not status.running:
            hint = "Ollama n'est pas démarré : lancez « ollama serve » puis rafraîchissez."
            if status.error:
                hint += f" ({status.error})"
            self.models_hint.setText(hint)
        elif not status.models:
            self.models_hint.setText(
                "Aucun modèle installé. Téléchargez-en un, par exemple : ollama pull llama3.1"
            )
        else:
            self.models_hint.setText(
                f"{len(status.models)} modèle(s) détecté(s). L'analyse utilise le modèle sélectionné."
            )

    def _on_model_changed(self, _text: str) -> None:
        self._update_start_button()

    def _update_start_button(self) -> None:
        has_model = bool(self.model_combo.currentText().strip())
        self.btn_analyze.setEnabled(has_model and self._worker is None)

    def _refresh_models(self) -> None:
        if self._worker is not None:
            return
        self.btn_refresh.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            status = ollama_client.get_status()
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_refresh.setEnabled(True)
        self._status = status
        self._populate_models(status)
        self._set_status("Liste des modèles actualisée." if status.running else "Ollama injoignable.")

    # ------------------------------------------------------------- analyse
    def _autostart(self) -> None:
        if self._worker is not None:
            return
        if not self.model_combo.currentText().strip():
            self._set_status(
                "Aucun modèle disponible. Installez-en un avec : ollama pull llama3.1",
                error=True,
            )
            return
        saved = str(QSettings(_SETTINGS_ORG, _SETTINGS_APP).value(_SETTINGS_MODEL_KEY, ""))
        if saved:
            # Modèle déjà choisi lors d'une analyse précédente : on relance directement.
            self._start_analysis()
            return
        self._set_status(
            "Choisissez un modèle puis cliquez sur « Analyser avec l'IA »."
        )

    def _start_analysis(self) -> None:
        if self._worker is not None:
            return

        model = self.model_combo.currentText().strip()
        if not model:
            self._set_status(
                "Aucun modèle disponible. Installez-en un avec : ollama pull llama3.1",
                error=True,
            )
            return

        self._save_model(model)
        self._content = ""
        self._thinking = ""
        self._error = ""
        self._stop_requested = False
        self._active_model = model
        self.answer.clear()
        self.thinking_view.clear()
        self.thinking_group.setVisible(False)
        self.btn_copy.setEnabled(False)

        self.model_combo.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.btn_analyze.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_status(f"Analyse en cours avec « {model} »…")

        self._worker = _OllamaWorker(model, self._prompt.messages, self)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _stop_analysis(self) -> None:
        if self._worker is None:
            return
        self._stop_requested = True
        self._worker.stop()
        self.btn_stop.setEnabled(False)
        self._set_status("Arrêt demandé…")

    def _on_chunk(self, kind: str, text: str) -> None:
        if kind == "thinking":
            self._thinking += text
            if not self.thinking_group.isVisible():
                self.thinking_group.setVisible(True)
            self._append(self.thinking_view, text)
            return
        self._content += text
        self._append(self.answer, text)

    @staticmethod
    def _append(edit: QTextEdit | QPlainTextEdit, text: str) -> None:
        edit.moveCursor(QTextCursor.MoveOperation.End)
        edit.insertPlainText(text)
        edit.moveCursor(QTextCursor.MoveOperation.End)

    def _on_failed(self, message: str) -> None:
        self._error = message

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        stopped = self._stop_requested or (worker is not None and worker.stopped)
        if worker is not None:
            worker.deleteLater()

        self.model_combo.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._update_start_button()

        has_content = bool(self._content.strip())
        self.btn_copy.setEnabled(has_content)
        if has_content:
            self.btn_analyze.setText("Relancer l'analyse")

        if stopped:
            self._set_status("Analyse interrompue.")
            return
        if self._error:
            self._set_status(self._error, error=True)
            if not has_content:
                self.answer.setPlainText("⚠ " + self._error)
            return
        if not has_content:
            self._set_status("Le modèle n'a renvoyé aucun texte.", error=True)
            return

        # Rendu Markdown en fin de flux (le stream reste en texte brut).
        self.answer.setMarkdown(self._content)
        if self._thinking:
            self.thinking_view.setPlainText(self._thinking)
        self._set_status(f"Analyse terminée avec « {self._active_model} ».")

    def _copy_analysis(self) -> None:
        if not self._content.strip():
            return
        QApplication.clipboard().setText(self._content)
        self._set_status("Analyse copiée dans le presse-papiers.")

    def _set_status(self, text: str, *, error: bool = False) -> None:
        color = "#ef5350" if error else "#787b86"
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(text)

    def _save_model(self, model: str) -> None:
        settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        settings.setValue(_SETTINGS_MODEL_KEY, model)

    # ----------------------------------------------------------- fermeture
    def closeEvent(self, event: QCloseEvent) -> None:
        worker = self._worker
        if worker is not None:
            self._stop_requested = True
            worker.stop()
            if not worker.wait(3000):
                worker.terminate()
                worker.wait(2000)
            self._worker = None
        super().closeEvent(event)
