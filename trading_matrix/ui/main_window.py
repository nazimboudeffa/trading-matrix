from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QStatusBar,
)

from trading_matrix.core import ollama_client
from trading_matrix.core.config import APP_NAME, WINDOW_HEIGHT, WINDOW_WIDTH
from trading_matrix.data.openbb_client import OpenBBClient
from trading_matrix.indicators.registry import IndicatorRegistry
from trading_matrix.strategies.engine import StrategyEngine
from trading_matrix.strategies.registry import StrategyRegistry
from trading_matrix.ui.ai_analysis_dialog import AIAnalysisDialog
from trading_matrix.ui.chart_widget import ChartWidget
from trading_matrix.ui.indicator_panel import IndicatorPanel
from trading_matrix.ui.markets_window import MarketsWindow
from trading_matrix.ui.strategy_panel import StrategyPanel
from trading_matrix.ui.strategy_table import SignalTable
from trading_matrix.ui.toolbar import Toolbar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.client = OpenBBClient()
        self.indicator_registry = IndicatorRegistry()
        self.strategy_registry = StrategyRegistry()
        self.strategy_engine = StrategyEngine(self.strategy_registry)
        self.current_symbol = ""
        self.current_interval = ""
        self.current_df = None
        self.last_selection = None
        self.signals = []
        self.ai_dialogs: list[AIAnalysisDialog] = []

        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        from PySide6.QtWidgets import QToolBar

        self.toolbar = Toolbar(self)
        tb = QToolBar("Toolbar", self)
        tb.setMovable(False)
        tb.addWidget(self.toolbar)
        self.addToolBar(tb)
        self.toolbar.loadRequested.connect(self.load_data)
        self.toolbar.marketsRequested.connect(self.open_markets_window)

        self.chart = ChartWidget(self)
        self.setCentralWidget(self.chart)

        # Le panneau Marchés vit dans sa propre fenêtre (non modale) pour ne
        # pas surcharger la fenêtre principale.
        self.markets_window = MarketsWindow(self)
        self.markets_window.instrumentActivated.connect(self.toolbar.request_load)

        self.sidebar = IndicatorPanel(self.indicator_registry, self)
        dock = QDockWidget("Indicateurs", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        dock.setWidget(self.sidebar)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self.strategy_panel = StrategyPanel(self.strategy_registry, self)
        dock3 = QDockWidget("Stratégies", self)
        dock3.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        dock3.setWidget(self.strategy_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock3)
        self.tabifyDockWidget(dock, dock3)

        self.signal_table = SignalTable(self)
        dock4 = QDockWidget("Signaux détectés", self)
        dock4.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
        dock4.setWidget(self.signal_table)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock4)
        dock4.setMinimumHeight(180)

        self.sidebar.indicatorsChanged.connect(self.apply_indicators)
        self.sidebar.clearRequested.connect(self.clear_indicators)
        self.strategy_panel.analyzeRequested.connect(self.run_strategy)
        self.strategy_panel.clearRequested.connect(self.clear_signals)
        self.signal_table.signalActivated.connect(self.focus_signal)
        self.signal_table.aiAnalysisRequested.connect(self.open_ai_analysis)

        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.status.showMessage("En attente de chargement...")

        self.toolbar.set_status("OpenBB/yfinance: " + ("OK" if self.client.is_available() else "DEMO"))

    def _apply_styles(self) -> None:
        qss_path = Path(__file__).parent / "styles.qss"
        if qss_path.exists():
            try:
                self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def open_markets_window(self) -> None:
        """Ouvre (ou ramène au premier plan) la fenêtre des marchés."""
        self.markets_window.show()
        self.markets_window.raise_()
        self.markets_window.activateWindow()

    def load_data(self, symbol: str, interval: str, period: str) -> None:
        self.status.showMessage(f"Chargement {symbol} {interval}/{period}...")
        try:
            df = self.client.get_ohlcv(symbol, interval=interval, period=period)
            self.current_df = df
            self.current_symbol = symbol
            self.current_interval = interval
            self.chart.set_data(df)
            self.signals = []
            self.signal_table.clear()
            self.status.showMessage(f"{symbol} | {len(df)} bougies | {interval} | {period}")
            # Réappliquer les indicateurs si déjà configurés
            if self.last_selection:
                self.apply_indicators(self.last_selection)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
            self.status.showMessage("Erreur de chargement")

    # ------------------------------------------------------------------ Stratégies
    def run_strategy(self, strategy_id: str, params: dict, filters: dict) -> None:
        if self.current_df is None:
            QMessageBox.information(self, "Info", "Charger des données d'abord.")
            return
        try:
            signals = self.strategy_engine.run(
                strategy_id,
                self.current_df,
                symbol=self.current_symbol,
                timeframe=self.current_interval,
                params=params,
                filters=filters,
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur stratégie", str(e))
            return

        self.signals = signals
        entry = self.strategy_registry.get(strategy_id)
        strategy_name = entry.name if entry else strategy_id
        for sig in signals:
            sig.meta.setdefault("strategy_id", strategy_id)
            sig.meta.setdefault("strategy_name", strategy_name)
            sig.meta.setdefault("symbol", self.current_symbol)
            sig.meta.setdefault("timeframe", self.current_interval)
        self.signal_table.set_signals(signals)
        self.strategy_panel.set_result(len(signals))

        from trading_matrix.charts.markers import draw_signals

        draw_signals(self.chart, signals)
        self.status.showMessage(f"{len(signals)} signal(aux) détecté(s)")

    # ------------------------------------------------------------------ IA
    def open_ai_analysis(self, sig) -> None:
        """Ouvre une fenêtre d'analyse IA pour le signal, après contrôle d'Ollama."""
        if self.current_df is None or len(self.current_df) == 0:
            QMessageBox.information(self, "Info", "Charger des données d'abord.")
            return

        status = ollama_client.get_status()
        if not status.installed:
            QMessageBox.warning(
                self,
                "Ollama introuvable",
                "Ollama n'est pas installé sur cet ordinateur.\n\n"
                "L'analyse IA locale nécessite Ollama.\n"
                "1. Téléchargez-le sur https://ollama.com/download\n"
                "2. Installez-le, puis lancez un modèle : ollama pull llama3.1\n"
                "3. Redémarrez l'application si Ollama n'est pas détecté.",
            )
            return
        if not status.running:
            QMessageBox.warning(
                self,
                "Ollama n'est pas démarré",
                "Ollama est installé mais son service ne répond pas.\n\n"
                "Démarrez-le avec la commande : ollama serve\n"
                "puis cliquez à nouveau sur « Analyser IA ».",
            )
            return
        if not status.models:
            QMessageBox.information(
                self,
                "Aucun modèle Ollama",
                "Ollama fonctionne mais aucun modèle n'est installé.\n\n"
                "Téléchargez un modèle, par exemple :\n"
                "    ollama pull llama3.1\n"
                "puis cliquez à nouveau sur « Analyser IA ».",
            )
            return

        strategy_id = sig.meta.get("strategy_id") or self.strategy_panel.current_strategy_id()
        entry = self.strategy_registry.get(strategy_id) if strategy_id else None
        strategy_name = sig.meta.get("strategy_name") or (entry.name if entry else "")
        strategy_description = entry.description if entry else ""

        dialog = AIAnalysisDialog(
            sig,
            self.current_df,
            symbol=self.current_symbol,
            timeframe=self.current_interval,
            strategy_name=strategy_name,
            strategy_description=strategy_description,
            status=status,
            parent=self,
        )
        dialog.destroyed.connect(lambda *_: self._forget_ai_dialog(dialog))
        self.ai_dialogs.append(dialog)

        geometry = self.frameGeometry()
        dialog.move(geometry.center() - dialog.rect().center())
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_ai_dialog(self, dialog: AIAnalysisDialog) -> None:
        if dialog in self.ai_dialogs:
            self.ai_dialogs.remove(dialog)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Ferme proprement les analyses en cours (arrêt des threads Ollama).
        for dialog in list(self.ai_dialogs):
            dialog.close()
        self.markets_window.shutdown()
        self.toolbar.symbol_completer.shutdown()
        super().closeEvent(event)

    def clear_signals(self) -> None:
        self.signals = []
        self.signal_table.clear()
        from trading_matrix.charts.markers import clear_signal_items

        clear_signal_items(self.chart)
        self.status.showMessage("Signaux effacés")

    def focus_signal(self, sig) -> None:
        """Met en évidence le signal cliqué et affiche ses niveaux dans la barre de statut."""
        from trading_matrix.charts.markers import draw_signals

        draw_signals(self.chart, self.signals, selected=sig)
        self.chart.focus_on_time(sig.time, span=80)

        rr = sig.meta.get("rr")
        statut = "En attente" if sig.meta.get("pending") else "Confirmé"
        self.status.showMessage(
            f"{statut} · {sig.side.value} {sig.confidence}% · entrée {sig.entry:.2f} "
            f"· SL {sig.sl:.2f} · TP1 {sig.tp1:.2f}"
            + (f" · R:R {rr}" if rr is not None else "")
        )

    def clear_indicators(self) -> None:
        self.last_selection = None
        self.chart.clear_indicators()

    def apply_indicators(self, selection: list) -> None:
        """Applique la liste [(id, params), ...] d'indicateurs cochés."""
        if self.current_df is None:
            QMessageBox.information(self, "Info", "Charger des données d'abord.")
            return
        self.last_selection = selection
        self.chart.clear_indicators()

        for cid, params in selection or []:
            try:
                res = self.indicator_registry.compute(cid, self.current_df, params)
            except Exception as e:
                QMessageBox.critical(self, "Erreur indicateur", f"{cid} : {e}")
                continue
            self._draw_indicator(res)

    def _draw_indicator(self, res) -> None:
        if res.kind == "overlay":
            for p in res.plots:
                self.chart.add_overlay(p.series, p.label, color=p.color, width=p.width)
        elif res.kind == "subplot":
            series_list = [(p.label, p.series, p.color) for p in res.plots]
            self.chart.add_subplot(res.name, series_list, height=res.height, hlines=res.hlines)
