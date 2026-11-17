"""Annotations Price Action : sobriété du graphique et mise en évidence au clic."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from trading_matrix.charts.markers import draw_signals
from trading_matrix.strategies.base import Side, Signal

# Garde une instance unique pour toute la session de tests.
_APP = QApplication.instance() or QApplication([])


def _chart(n: int = 120):
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame(
        {
            "Open": np.full(n, 100.0),
            "High": np.full(n, 101.0),
            "Low": np.full(n, 99.0),
            "Close": np.full(n, 100.0),
        },
        index=idx,
    )
    chart = type("FakeChart", (), {})()
    chart.df = df
    chart.n = n
    chart.price_plot = pg.PlotWidget()
    chart.signal_items = []
    return chart, idx


def _pending_signal(time) -> Signal:
    sig = Signal(
        time=time,
        side=Side.LONG,
        entry=100.0,
        sl=99.0,
        tp1=102.0,
        tp2=103.0,
        tp3=104.0,
        confidence=62,
        setup_type="OB_PENDING_BULL",
        zone_price_low=99.8,
        zone_price_high=100.2,
    )
    sig.meta.update({"pending": True, "rr": 2.0, "atr": 1.0})
    return sig


def test_pending_marker_is_on_last_candle() -> None:
    chart, idx = _chart()

    draw_signals(chart, [_pending_signal(idx[-1])])

    scatters = [it for it in chart.signal_items if isinstance(it, pg.ScatterPlotItem)]
    assert len(scatters) == 1
    assert scatters[0].getData()[0].tolist() == [chart.n - 1]


def test_details_are_on_hover_instead_of_permanent_text() -> None:
    chart, idx = _chart()

    draw_signals(chart, [_pending_signal(idx[-1])])

    assert not [it for it in chart.signal_items if isinstance(it, pg.TextItem)]
    assert not [it for it in chart.signal_items if isinstance(it, pg.InfiniteLine)]

    scatters = [it for it in chart.signal_items if isinstance(it, pg.ScatterPlotItem)]
    tip = scatters[0].toolTip()
    assert "À VENIR" in tip
    assert "LONG" in tip
    assert "Entrée 100.00" in tip
    assert "SL 99.00" in tip
    assert "TP1 102.00" in tip
    assert "R:R 2.00" in tip


def test_selected_signal_is_highlighted() -> None:
    chart, idx = _chart()
    sig = _pending_signal(idx[-1])

    draw_signals(chart, [sig], selected=sig)

    guides = [it for it in chart.signal_items if isinstance(it, pg.InfiniteLine)]
    assert len(guides) == 1
    assert guides[0].value() == chart.n - 1

    scatters = [it for it in chart.signal_items if isinstance(it, pg.ScatterPlotItem)]
    assert scatters[0].opts["size"] == 18
