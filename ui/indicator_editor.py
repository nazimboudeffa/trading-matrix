from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

TEMPLATE = '''import pandas as pd
import numpy as np

NAME = "Mon indicateur"
DESCRIPTION = "Décris ton indicateur ici"
PARAMS = {"period": 20}

def compute(df: pd.DataFrame, period: int = 20):
    from indicators.base import IndicatorResult, PlotItem

    ema = df["Close"].ewm(span=period, adjust=False).mean()

    return IndicatorResult(
        name=f"EMA perso ({period})",
        kind="overlay",  # "overlay" ou "subplot"
        plots=[PlotItem(label="EMA", series=ema, color="#9c27b0", width=2)],
    )
'''


class IndicatorEditorDialog(QDialog):
    def __init__(self, parent=None, filename: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Éditeur d'indicateur personnalisé")
        self.resize(900, 650)
        self.root = Path("user_indicators")
        self.root.mkdir(exist_ok=True)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Nom du fichier:"))
        self.name_edit = QLineEdit(filename or "mon_indicateur.py")
        top.addWidget(self.name_edit)
        layout.addLayout(top)

        self.editor = QTextEdit()
        self.editor.setPlainText(TEMPLATE)
        self.editor.setTabStopDistance(16)
        layout.addWidget(self.editor)

        bottom = QHBoxLayout()
        btn_open = QPushButton("Ouvrir dossier")
        btn_open.clicked.connect(self.open_folder)
        bottom.addWidget(btn_open)
        bottom.addStretch(1)
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(btn_cancel)
        btn_save = QPushButton("Enregistrer")
        btn_save.setObjectName("primaryButton")
        btn_save.clicked.connect(self.save)
        bottom.addWidget(btn_save)
        layout.addLayout(bottom)

    def open_folder(self):
        import os
        import subprocess

        path = self.root.resolve()
        try:
            os.startfile(path)
        except Exception:
            try:
                subprocess.Popen(["explorer", str(path)])
            except Exception:
                pass

    def save(self):
        name = self.name_edit.text().strip()
        if not name.endswith(".py"):
            name += ".py"
        if name.startswith("_"):
            QMessageBox.warning(self, "Erreur", "Le nom ne doit pas commencer par '_'")
            return
        path = self.root / name
        if path.exists():
            resp = QMessageBox.question(self, "Fichier existant", "Écraser le fichier existant ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return
        try:
            path.write_text(self.editor.toPlainText(), encoding="utf-8")
            QMessageBox.information(self, "OK", f"Enregistré: {path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
