"""Fenêtre d'analyse IA d'un signal via Llama App."""

from __future__ import annotations

import threading

from PySide6.QtCore import QSettings, Qt, QThread
from PySide6.QtCore import Signal as QtSignal
from PySide6.QtGui import QCloseEvent, QFont, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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

from trading_matrix.core import llama_client
from trading_matrix.core.signal_context import build_signal_prompt
from trading_matrix.data.openbb_client import NewsItem, OpenBBClient
from trading_matrix.strategies.base import Signal as TradeSignal

_SETTINGS_ORG = "TradingMatrix"
_SETTINGS_APP = "TradingMatrix"
_SETTINGS_MODEL_KEY = "ai/model"
_SETTINGS_NEWS_KEY = "ai/include_news"
_NEWS_LIMIT = 5


def _price(value: float | None) -> str:
    if value is None:
        return "n/d"
    if abs(value) < 1:
        return f"{value:.5f}"
    if abs(value) < 100:
        return f"{value:.3f}"
    return f"{value:.2f}"


class _LlamaWorker(QThread):
    """Exécute la requête Llama hors du thread UI."""

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
            for kind, text in llama_client.chat_stream(
                self._model, self._messages, stop_event=self._stop
            ):
                if self._stop.is_set():
                    return
                self.chunk.emit(kind, text)
        except Exception as exc:  # noqa: BLE001 - message affiché à l'utilisateur
            if not self._stop.is_set():
                self.failed.emit(str(exc))


class _NewsWorker(QThread):
    """Récupère les dernières actualités hors du thread UI."""

    loaded = QtSignal(int, object, str)  # generation, list[NewsItem], erreur

    def __init__(self, symbol: str, limit: int, generation: int, parent=None):
        super().__init__(parent)
        self._symbol = symbol
        self._limit = limit
        self._generation = generation

    def run(self) -> None:
        try:
            items = OpenBBClient().get_news(self._symbol, limit=self._limit)
        except Exception as exc:  # noqa: BLE001 - message affiché dans la fenêtre
            self.loaded.emit(self._generation, [], str(exc))
            return
        self.loaded.emit(self._generation, items, "")


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
        status: llama_client.LlamaStatus | None = None,
        parent=None,
    ):
        super().__init__(parent, Qt.WindowType.Window)

        self.signal = sig
        self.df = df
        self.symbol = symbol or str(sig.meta.get("symbol") or "")
        self.timeframe = timeframe or str(sig.meta.get("timeframe") or "")
        self.strategy_name = strategy_name or str(sig.meta.get("strategy_name") or "")
        self._strategy_description = strategy_description
        self._status = status or llama_client.get_status()
        self._prompt = build_signal_prompt(
            sig,
            df,
            symbol=self.symbol,
            timeframe=self.timeframe,
            strategy_name=self.strategy_name,
            strategy_description=strategy_description,
        )

        self._worker: _LlamaWorker | None = None
        self._news_worker: _NewsWorker | None = None
        self._news_generation = 0
        self._news: list[NewsItem] = []
        self._news_error = ""
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
        if self._load_news_setting():
            self.news_check.setChecked(True)
        else:
            self._set_status(
                "Prêt. Cliquez sur « Analyser avec l'IA » pour lancer l'analyse."
            )

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
        tp3 = " · TP3 " + _price(self.signal.tp3) if self.signal.tp3 is not None else ""
        pending = bool(self.signal.meta.get("pending"))
        status = "EN ATTENTE" if pending else "Confirmé"
        subtitle = QLabel(
            f"Signal du {self.signal.time:%Y-%m-%d %H:%M} · {status} · "
            f"{self.signal.setup_type} · Entrée {_price(entry)} · SL {_price(self.signal.sl)} · "
            f"TP1 {_price(self.signal.tp1)}{tp2}{tp3} · Confiance {self.signal.confidence} %"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("aiSubtitle")
        layout.addWidget(subtitle)

        if pending:
            condition = self.signal.meta.get("condition") or "réaction à confirmer dans la zone"
            condition_label = QLabel(f"Setup conditionnel — {condition}")
            condition_label.setObjectName("aiPending")
            condition_label.setWordWrap(True)
            layout.addWidget(condition_label)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Modèle Llama"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(240)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_row.addWidget(self.model_combo, 1)
        self.btn_refresh = QPushButton("Rafraîchir")
        self.btn_refresh.setToolTip("Rescanner les modèles disponibles dans Llama App")
        self.btn_refresh.clicked.connect(self._refresh_models)
        model_row.addWidget(self.btn_refresh)
        layout.addLayout(model_row)

        self.models_hint = QLabel("")
        self.models_hint.setObjectName("aiHint")
        self.models_hint.setWordWrap(True)
        layout.addWidget(self.models_hint)

        news_row = QHBoxLayout()
        self.news_check = QCheckBox("Inclure les dernières actualités (OpenBB)")
        self.news_check.setToolTip(
            "Ajoute au contexte les actualités les plus récentes de l'actif via "
            "OpenBB (repli yfinance). Elles peuvent être postérieures à la bougie "
            "du signal : le prompt le précise au modèle."
        )
        self.news_check.toggled.connect(self._on_news_toggled)
        news_row.addWidget(self.news_check)
        news_row.addStretch(1)
        layout.addLayout(news_row)

        splitter = QSplitter(Qt.Orientation.Vertical, self)

        prompt_group = QGroupBox("Contexte envoyé à l'IA")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_note = QLabel(
            "Texte exact transmis au modèle (bougies jusqu'à la dernière disponible ; "
            "actualités OpenBB uniquement si l'option est cochée)."
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
    def _populate_models(self, status: llama_client.LlamaStatus) -> None:
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
            hint = "Serveur Llama injoignable : lancez « llama serve » puis rafraîchissez."
            if status.error:
                hint += f" ({status.error})"
            self.models_hint.setText(hint)
        elif not status.models:
            self.models_hint.setText(
                "Aucun modèle installé. Installez-en un depuis l'application Llama "
                "ou avec : llama serve -hf ggml-org/gemma-4-e4b-it-GGUF:Q4_0"
            )
        else:
            self.models_hint.setText(
                f"{len(status.models)} modèle(s) détecté(s). L'analyse utilise le modèle sélectionné."
            )

    def _on_model_changed(self, _text: str) -> None:
        self._update_start_button()

    def _update_start_button(self) -> None:
        has_model = bool(self.model_combo.currentText().strip())
        news_pending = (
            getattr(self, "news_check", None) is not None
            and self.news_check.isChecked()
            and self._news_worker is not None
        )
        button = getattr(self, "btn_analyze", None)
        if button is not None:
            button.setEnabled(has_model and self._worker is None and not news_pending)

    def _refresh_models(self) -> None:
        if self._worker is not None:
            return
        self.btn_refresh.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            status = llama_client.get_status()
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_refresh.setEnabled(True)
        self._status = status
        self._populate_models(status)
        self._set_status("Liste des modèles actualisée." if status.running else "Llama injoignable.")

    # ------------------------------------------------------------ actualités
    @staticmethod
    def _load_news_setting() -> bool:
        value = QSettings(_SETTINGS_ORG, _SETTINGS_APP).value(_SETTINGS_NEWS_KEY, 0)
        try:
            return bool(int(value or 0))
        except (TypeError, ValueError):
            return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _save_news_setting(enabled: bool) -> None:
        QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(
            _SETTINGS_NEWS_KEY, 1 if enabled else 0
        )

    def _rebuild_prompt(self) -> None:
        """Reconstruit le prompt avec l'état courant des actualités."""
        include_news = self.news_check.isChecked()
        self._prompt = build_signal_prompt(
            self.signal,
            self.df,
            symbol=self.symbol,
            timeframe=self.timeframe,
            strategy_name=self.strategy_name,
            strategy_description=self._strategy_description,
            news=self._news if include_news else None,
            news_error=self._news_error if include_news else "",
        )
        if hasattr(self, "prompt_view"):
            self.prompt_view.setPlainText(self._prompt.display_text())

    def _on_news_toggled(self, checked: bool) -> None:
        self._save_news_setting(checked)
        self._news_generation += 1

        if not checked:
            self._news = []
            self._news_error = ""
            self._rebuild_prompt()
            self._set_status("Actualités désactivées : contexte sans news.")
            self._update_start_button()
            return

        if not self.symbol:
            self._news = []
            self._news_error = "symbole non renseigné"
            self._rebuild_prompt()
            self._set_status(
                "Impossible de récupérer les actualités : symbole non renseigné.",
                error=True,
            )
            self._update_start_button()
            return

        self._news = []
        self._news_error = ""
        self._set_status(
            f"Récupération des actualités de « {self.symbol} » via OpenBB…"
        )
        self._start_news_fetch(self._news_generation)

    def _start_news_fetch(self, generation: int) -> None:
        worker = _NewsWorker(self.symbol, _NEWS_LIMIT, generation, self)
        worker.loaded.connect(self._on_news_loaded)
        worker.finished.connect(lambda w=worker: self._forget_news_worker(w))
        self._news_worker = worker
        self._update_start_button()
        worker.start()

    def _on_news_loaded(self, generation: int, items: object, error: str) -> None:
        if generation != self._news_generation:
            return
        self._news = (
            [item for item in items if isinstance(item, NewsItem)]
            if isinstance(items, list)
            else []
        )
        self._news_error = error
        self._rebuild_prompt()

        if error:
            self._set_status(f"Actualités indisponibles : {error}", error=True)
        elif self._news:
            self._set_status(f"{len(self._news)} actualité(s) ajoutée(s) au contexte.")
        else:
            self._set_status("Aucune actualité récente trouvée pour ce symbole.")
        self._update_start_button()

    def _forget_news_worker(self, worker: _NewsWorker) -> None:
        if self._news_worker is worker:
            self._news_worker = None
        worker.deleteLater()
        self._update_start_button()

    # ------------------------------------------------------------- analyse
    def _start_analysis(self) -> None:
        if self._worker is not None:
            return
        if self._news_worker is not None and self.news_check.isChecked():
            self._set_status("Récupération des actualités en cours…")
            return

        model = self.model_combo.currentText().strip()
        if not model:
            self._set_status(
                "Aucun modèle disponible. Installez-en un depuis l'application Llama "
                "ou avec : llama serve -hf ggml-org/gemma-4-e4b-it-GGUF:Q4_0",
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

        self._worker = _LlamaWorker(model, self._prompt.messages, self)
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
        news_worker = self._news_worker
        if news_worker is not None:
            self._news_worker = None
            news_worker.requestInterruption()
            if not news_worker.wait(2000):
                news_worker.terminate()
                news_worker.wait(1000)
        super().closeEvent(event)
