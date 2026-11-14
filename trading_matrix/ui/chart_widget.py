from __future__ import annotations

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPicture
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from core.config import PALETTE


class CandlestickItem(pg.GraphicsObject):
    """Item pyqtgraph dessinant un graphique en chandeliers japonais."""

    def __init__(self, data: np.ndarray):
        """
        data: np.ndarray de forme (N, 5) = [x, open, high, low, close]
        """
        super().__init__()
        self.data = data
        self.picture = QPicture()
        self._generate_picture()

    def _generate_picture(self) -> None:
        self.picture = QPicture()
        painter = QPainter(self.picture)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        width = 0.6
        up_color = QColor(PALETTE["up"])
        down_color = QColor(PALETTE["down"])

        for x, o, h, l, c in self.data:
            if c >= o:
                color = up_color
                body_top, body_bottom = c, o
            else:
                color = down_color
                body_top, body_bottom = o, c

            # Mèche
            painter.setPen(pg.mkPen(color, width=1))
            painter.drawLine(QPointF(x, l), QPointF(x, h))

            # Corps (éviter corps de hauteur nulle)
            if abs(body_top - body_bottom) < 1e-9:
                painter.drawLine(
                    QPointF(x - width / 2, body_top),
                    QPointF(x + width / 2, body_top),
                )
            else:
                painter.setBrush(pg.mkBrush(color))
                painter.drawRect(
                    QRectF(
                        x - width / 2,
                        body_bottom,
                        width,
                        body_top - body_bottom,
                    )
                )
        painter.end()

    def paint(self, painter, option, widget=None) -> None:
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        if len(self.data) == 0:
            return QRectF()
        x_min = float(self.data[:, 0].min()) - 1
        x_max = float(self.data[:, 0].max()) + 1
        y_min = float(self.data[:, 3].min())
        y_max = float(self.data[:, 2].max())
        return QRectF(x_min, y_min, x_max - x_min, y_max - y_min)


class ChartWidget(QWidget):
    """Widget principal : chandeliers + volume + panneaux indicateurs."""

    hoverInfo = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df: pd.DataFrame | None = None
        self.dates: pd.DatetimeIndex | None = None
        self.indicator_series: dict[str, list[pg.PlotDataItem]] = {}
        self.subplot_count = 0
        self.signal_items: list = []

        self._build_ui()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(2)
        layout.addWidget(self.splitter)

        # --- Graphique principal
        self.price_plot = pg.PlotWidget()
        self.price_plot.setBackground(PALETTE["bg"])
        self.price_plot.showGrid(x=True, y=True, alpha=0.15)
        self.price_plot.setMouseEnabled(x=True, y=False)
        self.price_plot.hideAxis("bottom")
        self.price_plot.getAxis("left").setTextPen(PALETTE["text_sub"])
        self.price_plot.getAxis("left").setPen(PALETTE["grid"])
        self.splitter.addWidget(self.price_plot)

        # --- Volume
        self.volume_plot = pg.PlotWidget()
        self.volume_plot.setBackground(PALETTE["bg"])
        self.volume_plot.showGrid(x=True, y=True, alpha=0.10)
        self.volume_plot.setMouseEnabled(x=True, y=False)
        self.volume_plot.setMaximumHeight(140)
        self.volume_plot.hideAxis("left")
        self.volume_plot.getAxis("bottom").setTextPen(PALETTE["text_sub"])
        self.volume_plot.getAxis("bottom").setPen(PALETTE["grid"])
        self.splitter.addWidget(self.volume_plot)

        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 1)

        # Crosshair + labels
        self.vline_price = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(PALETTE["cross"], width=1, style=Qt.PenStyle.DashLine))
        self.hline_price = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(PALETTE["cross"], width=1, style=Qt.PenStyle.DashLine))
        self.price_plot.addItem(self.vline_price, ignoreBounds=True)
        self.price_plot.addItem(self.hline_price, ignoreBounds=True)

        self.vline_volume = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(PALETTE["cross"], width=1, style=Qt.PenStyle.DashLine))
        self.volume_plot.addItem(self.vline_volume, ignoreBounds=True)

        self.price_label = pg.TextItem("", color=PALETTE["text"], anchor=(0, 1), fill=pg.mkBrush(30, 34, 45, 220))
        self.price_plot.addItem(self.price_label, ignoreBounds=True)

        # Synchronisation du zoom / pan
        self.volume_plot.setXLink(self.price_plot)

        # Signaux souris
        self.price_plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.volume_plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Indicateurs stockés dans le plot principal (superposés)
        self.overlay_items: list[pg.PlotDataItem] = []

    # ---------------------------------------------------------------- Data
    def set_data(self, df: pd.DataFrame) -> None:
        """Charge un DataFrame OHLCV et affiche chandeliers + volume."""
        self.df = df.copy()
        self.dates = df.index
        self.n = len(df)
        self.x = np.arange(self.n, dtype=float)

        from charts.markers import clear_signal_items

        clear_signal_items(self)

        self._clear_plots()

        # Chandeliers
        candle_data = np.column_stack([
            self.x,
            df["Open"].to_numpy(dtype=float),
            df["High"].to_numpy(dtype=float),
            df["Low"].to_numpy(dtype=float),
            df["Close"].to_numpy(dtype=float),
        ])
        self.candles = CandlestickItem(candle_data)
        self.price_plot.addItem(self.candles)

        # Volume
        if "Volume" in df.columns:
            volumes = df["Volume"].to_numpy(dtype=float)
            closes = df["Close"].to_numpy(dtype=float)
            opens = df["Open"].to_numpy(dtype=float)
            self._draw_volume(self.x, volumes, closes >= opens)

        # Axe X : labels de dates
        self._set_date_axis()

        # Ajuster la vue
        self.price_plot.setXRange(0, self.n, padding=0.02)
        self.price_plot.enableAutoRange(axis="y")
        self.price_plot.autoRange()

        self.price_plot.update()
        self.volume_plot.update()

    def _draw_volume(self, x: np.ndarray, volumes: np.ndarray, up: np.ndarray) -> None:
        brushes = np.where(up, pg.mkColor(PALETTE["volume_up"]), pg.mkColor(PALETTE["volume_down"])).tolist()
        self.volume_bars = pg.BarGraphItem(
            x=x, height=volumes, width=0.6, brushes=brushes, pen=None
        )
        self.volume_plot.addItem(self.volume_bars)

    def _set_date_axis(self) -> None:
        if self.dates is None or len(self.dates) == 0:
            return

        # Sélectionner ~8 ticks
        step = max(1, self.n // 8)
        ticks = []
        for i in range(0, self.n, step):
            ticks.append((i, self.dates[i].strftime("%Y-%m-%d" if self.n > 200 else "%m-%d %H:%M")))

        axis = self.volume_plot.getAxis("bottom")
        axis.setTicks([ticks])
        axis.setLabel("")

        # Masquer les ticks du plot principal
        self.price_plot.getAxis("bottom").setTicks([[]])

    def _clear_plots(self) -> None:
        # Nettoyer les éléments précédents
        if hasattr(self, "candles") and self.candles is not None:
            self.price_plot.removeItem(self.candles)
            self.candles = None
        if hasattr(self, "volume_bars") and self.volume_bars is not None:
            self.volume_plot.removeItem(self.volume_bars)
            self.volume_bars = None

        for item in self.overlay_items:
            self.price_plot.removeItem(item)
        self.overlay_items.clear()

        for key, items in list(self.indicator_series.items()):
            for item in items:
                try:
                    self.price_plot.removeItem(item)
                except Exception:
                    pass
        self.indicator_series.clear()

        # Supprimer sous-graphiques
        while self.subplot_count > 0:
            widget = self.splitter.widget(2)
            if widget is None:
                break
            widget.deleteLater()
            self.subplot_count -= 1

    # ---------------------------------------------------------------- Indicators
    def add_overlay(self, series: pd.Series, name: str, color: str = "#f0b90b", width: int = 2) -> None:
        if self.df is None:
            return
        pen = pg.mkPen(color, width=width)
        item = pg.PlotDataItem(self.x, series.to_numpy(dtype=float), pen=pen, name=name)
        self.price_plot.addItem(item)
        self.overlay_items.append(item)
        self.indicator_series.setdefault(name, []).append(item)

    def add_bollinger(self, upper: pd.Series, mid: pd.Series, lower: pd.Series) -> None:
        if self.df is None:
            return
        pen = pg.mkPen(PALETTE["bb"], width=1, style=Qt.PenStyle.DashLine)
        for s in (upper, mid, lower):
            item = pg.PlotDataItem(self.x, s.to_numpy(dtype=float), pen=pen)
            self.price_plot.addItem(item)
            self.overlay_items.append(item)
        # Remplissage optionnel
        try:
            fill = pg.FillBetweenItem(
                self.overlay_items[-3], self.overlay_items[-1],
                brush=pg.mkBrush(120, 123, 134, 25),
            )
            self.price_plot.addItem(fill)
            self.overlay_items.append(fill)
        except Exception:
            pass

    def add_subplot(self, title: str, series_list: list[tuple[str, pd.Series, str]], height: int = 120, hlines=None):
        """Ajoute un panneau indicateur en dessous (RSI, MACD, etc.).

        hlines: liste optionnelle de tuples (valeur, couleur) pour tracer des
        lignes horizontales de référence.
        """
        if self.df is None:
            return None

        plot = pg.PlotWidget()
        plot.setBackground(PALETTE["bg"])
        plot.showGrid(x=True, y=True, alpha=0.10)
        plot.setMaximumHeight(height)
        plot.setMouseEnabled(x=True, y=False)
        plot.setXLink(self.price_plot)
        plot.getAxis("left").setTextPen(PALETTE["text_sub"])
        plot.getAxis("left").setPen(PALETTE["grid"])
        plot.getAxis("bottom").setTextPen(PALETTE["text_sub"])
        plot.getAxis("bottom").setPen(PALETTE["grid"])
        plot.setTitle(title, color=PALETTE["text_sub"], size="9pt")

        items = []
        for name, series, color in series_list:
            if isinstance(series, pd.Series):
                pen = pg.mkPen(color, width=1)
                item = plot.plot(self.x, series.to_numpy(dtype=float), pen=pen, name=name)
                items.append(item)

        if hlines:
            for value, color in hlines:
                try:
                    line = pg.InfiniteLine(
                        pos=float(value),
                        angle=0,
                        pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine),
                    )
                    plot.addItem(line, ignoreBounds=True)
                except Exception:
                    pass

        self.splitter.addWidget(plot)
        self.subplot_count += 1
        self.subpanel_items = getattr(self, "subpanel_items", [])
        self.subpanel_items.append((plot, items))

        # Crosshair vertical sur le sous-graphique
        vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(PALETTE["cross"], width=1, style=Qt.PenStyle.DashLine))
        plot.addItem(vline, ignoreBounds=True)
        self.subpanel_vlines = getattr(self, "subpanel_vlines", [])
        self.subpanel_vlines.append(vline)
        plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        return plot

    def clear_indicators(self) -> None:
        for item in self.overlay_items:
            try:
                self.price_plot.removeItem(item)
            except Exception:
                pass
        self.overlay_items.clear()

        for key, items in list(self.indicator_series.items()):
            for item in items:
                try:
                    self.price_plot.removeItem(item)
                except Exception:
                    pass
        self.indicator_series.clear()

        for plot, items in getattr(self, "subpanel_items", []):
            plot.deleteLater()
        self.subpanel_items = []
        self.subplot_count = 0

    # ---------------------------------------------------------------- Interaction
    def _on_mouse_moved(self, pos) -> None:
        if self.df is None:
            return

        vb = self.price_plot.getViewBox()
        if not self.price_plot.sceneBoundingRect().contains(pos):
            # Quand la souris est sur un sous-graphique, récupérer son viewbox
            for plot, _ in getattr(self, "subpanel_items", []):
                if plot.sceneBoundingRect().contains(pos):
                    vb = plot.getViewBox()
                    break
            else:
                return

        mouse_point = vb.mapSceneToView(pos)
        idx = int(round(mouse_point.x()))

        if idx < 0 or idx >= self.n:
            return

        x = float(self.x[idx])
        self.vline_price.setPos(x)
        self.vline_volume.setPos(x)
        self.hline_price.setPos(self.df["Close"].iloc[idx])

        for vline in getattr(self, "subpanel_vlines", []):
            vline.setPos(x)

        row = self.df.iloc[idx]
        date_str = self.dates[idx].strftime("%Y-%m-%d %H:%M")
        text = (
            f"{date_str}   "
            f"O {row['Open']:.2f}  H {row['High']:.2f}  "
            f"L {row['Low']:.2f}  C {row['Close']:.2f}"
        )
        if "Volume" in row:
            text += f"  V {int(row['Volume']):,}"

        self.price_label.setText(text)
        self.price_label.setPos(x, float(self.df["High"].iloc[idx]))
        self.hoverInfo.emit(text)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.df is not None:
            self.price_plot.autoRange()

    def focus_on_time(self, ts, span: int = 60) -> None:
        """Centre la vue sur un timestamp donné (navigation depuis les signaux)."""
        if self.dates is None or self.n == 0:
            return
        try:
            idx = int(self.dates.get_loc(ts))
        except Exception:
            return
        half = max(5, span // 2)
        lo = max(0, idx - half)
        hi = min(self.n - 1, idx + half)
        if hi <= lo:
            hi = min(self.n - 1, lo + 10)
        self.price_plot.setXRange(lo, hi, padding=0)
