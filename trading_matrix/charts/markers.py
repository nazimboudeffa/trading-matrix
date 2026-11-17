from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsRectItem

from trading_matrix.core.config import PALETTE
from trading_matrix.strategies.base import Signal


def clear_signal_items(chart) -> None:
    for item in getattr(chart, "signal_items", []):
        try:
            chart.price_plot.removeItem(item)
        except Exception:
            pass
    chart.signal_items = []

    # Rétablit la plage normale après l'affichage d'éventuels signaux.
    if getattr(chart, "df", None) is not None and getattr(chart, "n", 0):
        chart.price_plot.setXRange(0, chart.n, padding=0.02)


def draw_signals(chart, signals, *, selected: Signal | None = None) -> None:
    """Dessine flèches, zones et SL/TP pour une liste de Signal.

    Le graphique reste sobre : pas de texte permanent, les détails sont
    accessibles au survol. Si ``selected`` est fourni, ce signal est mis en
    évidence (marqueur agrandi, zone renforcée et repère vertical).
    """
    clear_signal_items(chart)
    if chart.df is None or not signals:
        return

    chart.signal_items = getattr(chart, "signal_items", [])

    dates = list(chart.df.index)
    date_map = {ts: idx for idx, ts in enumerate(dates)}
    n = len(dates)
    last_range = float(chart.df["High"].iloc[-1] - chart.df["Low"].iloc[-1])

    for sig in signals:
        is_pending = bool(sig.meta.get("pending"))
        is_selected = selected is not None and sig is selected

        if is_pending:
            # Le plan d'entrée est attaché à la dernière bougie, pas à une
            # position fictive dans le futur.
            idx = n - 1
            x = float(idx)
        else:
            idx = date_map.get(sig.time)
            if idx is None:
                try:
                    idx = int(np.searchsorted(np.array(dates), np.datetime64(sig.time)))
                except Exception:
                    continue
            if idx < 0 or idx >= n:
                continue
            x = float(idx)

        is_long = sig.side.value == "LONG"
        if is_pending:
            color = PALETTE["pending"]
        else:
            color = PALETTE["up"] if is_long else PALETTE["down"]
        y = float(sig.entry)

        # Détails au survol : le graphique reste lisible même avec beaucoup de signaux.
        rr = sig.meta.get("rr")
        rr_txt = f" · R:R {rr:.2f}" if isinstance(rr, (int, float)) and np.isfinite(rr) else ""
        tip = (
            f"{'À VENIR' if is_pending else 'DÉCLENCHÉ'} {sig.side.value} · {sig.confidence}%{rr_txt}\n"
            f"Entrée {sig.entry:.2f} · SL {sig.sl:.2f} · TP1 {sig.tp1:.2f}\n"
            f"{sig.setup_type}"
        )

        # ---- Zone (bande horizontale autour du signal)
        if sig.zone_price_low is not None and sig.zone_price_high is not None:
            if is_pending:
                x1 = max(0, n - 12)
                x2 = float(n - 1)
            else:
                x1 = max(0, idx - 12)
                x2 = min(n - 1, idx + 18)
            bottom = float(sig.zone_price_low)
            top = float(sig.zone_price_high)
            rect = QGraphicsRectItem(x1, bottom, max(x2 - x1, 1), max(top - bottom, 1e-6))
            qc = QColor(color)
            qc.setAlpha(90 if is_selected else (35 if is_pending else 45))
            rect.setBrush(pg.mkBrush(qc))
            rect.setPen(
                pg.mkPen(
                    color,
                    width=2 if is_selected else 1,
                    style=Qt.PenStyle.SolidLine if is_selected or not is_pending else Qt.PenStyle.DashLine,
                )
            )
            rect.setToolTip(tip)
            chart.price_plot.addItem(rect)
            chart.signal_items.append(rect)

        if is_pending:
            atr_val = sig.meta.get("atr")
            offset = float(atr_val) * 0.5 if atr_val else last_range * 0.6 or 0.5
        else:
            offset = (chart.df["High"].iloc[idx] - chart.df["Low"].iloc[idx]) * 0.6 or 0.5

        # ---- Marqueur
        if is_pending:
            marker = pg.ScatterPlotItem(
                [x],
                [y],
                symbol="d",
                size=18 if is_selected else 13,
                brush=pg.mkBrush(0, 0, 0, 0),
                pen=pg.mkPen(color, width=2.6 if is_selected else 1.6),
            )
            marker.setToolTip(tip)
            chart.price_plot.addItem(marker)
            chart.signal_items.append(marker)
        else:
            arrow = pg.ArrowItem(
                angle=90 if is_long else -90,
                tipAngle=28,
                headLen=18 if is_selected else 14,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color, width=2 if is_selected else 1),
            )
            arrow.setPos(x, y - offset if is_long else y + offset)
            arrow.setToolTip(tip)
            chart.price_plot.addItem(arrow)
            chart.signal_items.append(arrow)

        # ---- Repère vertical pour le signal sélectionné dans la liste
        if is_selected:
            guide = pg.InfiniteLine(
                pos=x,
                angle=90,
                pen=pg.mkPen(color, width=1.2, style=Qt.PenStyle.DashLine),
            )
            chart.price_plot.addItem(guide)
            chart.signal_items.append(guide)

        # ---- SL / TP
        if is_pending:
            # Niveaux projetés sur les bougies disponibles, à gauche du signal.
            start = max(0, x - 3)
            end = x
        else:
            start = x
            end = min(n - 1, idx + 25)
            if end <= idx:
                end = min(n - 1, idx + 1)
        lines = [
            ("SL", sig.sl, "#ef5350"),
            ("TP1", sig.tp1, "#26a69a"),
        ]
        if sig.tp2 is not None:
            lines.append(("TP2", sig.tp2, "#4caf50"))
        if sig.tp3 is not None:
            lines.append(("TP3", sig.tp3, "#81c784"))

        for name, price, line_color in lines:
            item = pg.PlotDataItem(
                [start, end],
                [float(price), float(price)],
                pen=pg.mkPen(
                    line_color,
                    width=2 if is_selected else 1,
                    style=Qt.PenStyle.SolidLine if is_selected else Qt.PenStyle.DashLine,
                ),
            )
            item.setToolTip(f"{name} {float(price):.2f}\n{tip}")
            chart.price_plot.addItem(item)
            chart.signal_items.append(item)

    chart.price_plot.update()
