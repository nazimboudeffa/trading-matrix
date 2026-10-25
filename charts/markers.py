from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsRectItem

from core.config import PALETTE


def clear_signal_items(chart) -> None:
    for item in getattr(chart, "signal_items", []):
        try:
            chart.price_plot.removeItem(item)
        except Exception:
            pass
    chart.signal_items = []


def draw_signals(chart, signals) -> None:
    """Dessine flèches, zones, SL/TP et labels pour une liste de Signal."""
    clear_signal_items(chart)
    if chart.df is None or not signals:
        return

    chart.signal_items = getattr(chart, "signal_items", [])

    dates = list(chart.df.index)
    date_map = {ts: idx for idx, ts in enumerate(dates)}
    n = len(dates)

    for sig in signals:
        idx = date_map.get(sig.time)
        if idx is None:
            try:
                idx = int(np.searchsorted(np.array(dates), np.datetime64(sig.time)))
            except Exception:
                continue
        if idx < 0 or idx >= n:
            continue

        is_long = sig.side.value == "LONG"
        color = PALETTE["up"] if is_long else PALETTE["down"]
        y = float(sig.entry)

        # ---- Zone (bande horizontale autour du signal)
        if sig.zone_price_low is not None and sig.zone_price_high is not None:
            x1 = max(0, idx - 12)
            x2 = min(n - 1, idx + 18)
            bottom = float(sig.zone_price_low)
            top = float(sig.zone_price_high)
            rect = QGraphicsRectItem(x1, bottom, max(x2 - x1, 1), max(top - bottom, 1e-6))
            qc = QColor(color)
            qc.setAlpha(45)
            rect.setBrush(pg.mkBrush(qc))
            rect.setPen(pg.mkPen(color, width=1))
            chart.price_plot.addItem(rect)
            chart.signal_items.append(rect)

        # ---- Flèche
        offset = (chart.df["High"].iloc[idx] - chart.df["Low"].iloc[idx]) * 0.6 or 0.5
        arrow = pg.ArrowItem(
            angle=90 if is_long else -90,
            tipAngle=28,
            headLen=14,
            brush=pg.mkBrush(color),
            pen=pg.mkPen(color),
        )
        arrow.setPos(idx, y - offset if is_long else y + offset)
        chart.price_plot.addItem(arrow)
        chart.signal_items.append(arrow)

        # ---- Label
        label = pg.TextItem(
            f"{sig.side.value[:1]} {sig.confidence}%",
            color=color,
            anchor=(0.5, 1.2 if is_long else -0.2),
        )
        label.setPos(idx, y - offset if is_long else y + offset)
        chart.price_plot.addItem(label)
        chart.signal_items.append(label)

        # ---- SL / TP
        end = min(n - 1, idx + 25)
        if end <= idx:
            end = min(n - 1, idx + 1)
        lines = [
            ("SL", sig.sl, "#ef5350"),
            ("TP1", sig.tp1, "#26a69a"),
        ]
        if sig.tp2 is not None:
            lines.append(("TP2", sig.tp2, "#4caf50"))

        for name, price, line_color in lines:
            item = pg.PlotDataItem(
                [idx, end],
                [float(price), float(price)],
                pen=pg.mkPen(line_color, width=1, style=Qt.PenStyle.DashLine),
            )
            chart.price_plot.addItem(item)
            chart.signal_items.append(item)

    chart.price_plot.update()
