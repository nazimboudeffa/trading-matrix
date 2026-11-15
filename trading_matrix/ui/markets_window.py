"""Fenêtre autonome « Marchés ».

Le panneau Marchés (liste des constituants d'un indice) est présenté dans une
fenêtre séparée afin de ne pas surcharger la fenêtre principale. Elle s'ouvre
depuis le bouton « Marchés » de la barre d'outils.

La fenêtre est **non modale** : le graphique reste visible et se met à jour
lorsqu'un instrument est chargé par un double-clic dans le tableau.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout

from trading_matrix.ui.markets_panel import MarketsPanel


class MarketsWindow(QDialog):
    """Fenêtre non modale contenant le panneau « Marchés »."""

    instrumentActivated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Marchés")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setModal(False)
        self.resize(560, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = MarketsPanel(self)
        self.panel.instrumentActivated.connect(self.instrumentActivated)
        layout.addWidget(self.panel)

    def shutdown(self) -> None:
        """Arrête les chargements en cours (fermeture de l'application)."""
        self.panel.shutdown()
