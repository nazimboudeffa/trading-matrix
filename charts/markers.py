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

    # Les signaux à venir étendent la vue à droite : on rétablit la plage normale.
    if getattr(chart, "df", None) is not None and getattr(chart, "n", 0):
        chart.price_plot.setXRange(0, chart.n, padding=0.02)


def draw_signals(chart, signals) -> None:
    """Dessine flèches, zones, SL/TP et labels pour une liste de Signal.

    Les signaux à venir (``meta["pending"]``) sont projetés dans une marge à
    droite de la dernière bougie, avec un marqueur creux et un trait pointillé.
    """
    clear_signal_items(chart)
    if chart.df is None or not signals:
        return

    chart.signal_items = getattr(chart, "signal_items", [])

    dates = list(chart.df.index)
    date_map = {ts: idx for idx, ts in enumerate(dates)}
    n = len(dates)
    last_range = float(chart.df["High"].iloc[-1] - chart.df["Low"].iloc[-1])
    pending_offset = 0

    for sig in signals:
        is_pending = bool(sig.meta.get("pending"))

        if is_pending:
            # Position fictive à droite de la dernière bougie (marge « futur »).
            x = n - 1 + 3 + 4 * pending_offset
            pending_offset += 1
            idx = n - 1
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

        # ---- Zone (bande horizontale autour du signal)
        if sig.zone_price_low is not None and sig.zone_price_high is not None:
            if is_pending:
                x1 = max(0, n - 1 - 8)
                x2 = x + 12
            else:
                x1 = max(0, idx - 12)
                x2 = min(n - 1, idx + 18)
            bottom = float(sig.zone_price_low)
            top = float(sig.zone_price_high)
            rect = QGraphicsRectItem(x1, bottom, max(x2 - x1, 1), max(top - bottom, 1e-6))
            qc = QColor(color)
            qc.setAlpha(35 if is_pending else 45)
            rect.setBrush(pg.mkBrush(qc))
            rect.setPen(
                pg.mkPen(
                    color,
                    width=1,
                    style=Qt.PenStyle.DashLine if is_pending else Qt.PenStyle.SolidLine,
                )
            )
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
                size=13,
                brush=pg.mkBrush(0, 0, 0, 0),
                pen=pg.mkPen(color, width=1.6),
            )
            chart.price_plot.addItem(marker)
            chart.signal_items.append(marker)
            label_y = y - offset if is_long else y + offset
            label_text = f"{sig.side.value[:1]} {sig.confidence}% · à venir"
        else:
            arrow = pg.ArrowItem(
                angle=90 if is_long else -90,
                tipAngle=28,
                headLen=14,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color),
            )
            arrow.setPos(x, y - offset if is_long else y + offset)
            chart.price_plot.addItem(arrow)
            chart.signal_items.append(arrow)
            label_y = y - offset if is_long else y + offset
            label_text = f"{sig.side.value[:1]} {sig.confidence}%"

        # ---- Label
        label = pg.TextItem(
            label_text,
            color=color,
            anchor=(0.5, 1.2 if is_long else -0.2),
        )
        label.setPos(x, label_y)
        chart.price_plot.addItem(label)
        chart.signal_items.append(label)

        # ---- SL / TP
        if is_pending:
            end = x + 8
        else:
            end = min(n - 1, idx + 25)
            if end <= idx:
                end = min(n - 1, idx + 1)
        lines = [
            ("SL", sig.sl, "#ef5350"),
            ("TP1", sig.tp1, "#26a69a"),
        ]
        if sig.tp2 is not None:
            lines.append(("TP2", sig.tp2, "#4caf50"))

        for _name, price, line_color in lines:
            item = pg.PlotDataItem(
                [x, end],
                [float(price), float(price)],
                pen=pg.mkPen(line_color, width=1, style=Qt.PenStyle.DashLine),
            )
            chart.price_plot.addItem(item)
            chart.signal_items.append(item)

    if pending_offset:
        last_x = n - 1 + 3 + 4 * (pending_offset - 1)
        chart.price_plot.setXRange(0, last_x + 10, padding=0.02)

    chart.price_plot.update()
