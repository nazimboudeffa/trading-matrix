"""Tests du prompt d'analyse IA (aucun accès réseau)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from trading_matrix.core.signal_context import build_signal_prompt
from trading_matrix.data.openbb_client import NewsItem
from trading_matrix.strategies.base import Side, Signal


def _prices(periods: int = 60) -> pd.DataFrame:
    index = pd.date_range("2026-09-01", periods=periods, freq="D")
    close = pd.Series(range(100, 100 + periods), index=index, dtype=float)
    return pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": 1_000,
        },
        index=index,
    )


def _signal(df: pd.DataFrame) -> Signal:
    return Signal(
        time=df.index[-1],
        side=Side.LONG,
        entry=float(df["Close"].iloc[-1]),
        sl=float(df["Close"].iloc[-1]) - 5,
        tp1=float(df["Close"].iloc[-1]) + 10,
        tp2=float(df["Close"].iloc[-1]) + 20,
        confidence=60,
        setup_type="test",
        meta={"symbol": "AAPL", "timeframe": "1d"},
    )


def _news() -> list[NewsItem]:
    return [
        NewsItem(
            title="Résultats trimestriels supérieurs aux attentes",
            publisher="Reuters",
            published_at=datetime(2026, 11, 16, 14, 30, tzinfo=timezone.utc),
            summary="Le chiffre d'affaires progresse de 8 % sur un an.",
        ),
        NewsItem(
            title="Un analyste relève son objectif de cours",
            publisher="Bloomberg",
            published_at=datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc),
        ),
    ]


def test_prompt_sans_news_ne_contient_pas_de_section():
    df = _prices()
    prompt = build_signal_prompt(_signal(df), df, symbol="AAPL", timeframe="1d")
    assert "## Actualités récentes" not in prompt.user


def test_prompt_avec_news_ajoute_titres_et_avertissement():
    df = _prices()
    prompt = build_signal_prompt(
        _signal(df),
        df,
        symbol="AAPL",
        timeframe="1d",
        news=_news(),
    )
    assert "## Actualités récentes" in prompt.user
    assert "Résultats trimestriels supérieurs aux attentes" in prompt.user
    assert "Reuters" in prompt.user
    assert "2026-11-16 14:30 UTC" in prompt.user
    assert "Bloomberg" in prompt.user
    assert "postérieures" in prompt.user


def test_prompt_avec_news_vides_indique_absence():
    df = _prices()
    prompt = build_signal_prompt(
        _signal(df),
        df,
        symbol="AAPL",
        timeframe="1d",
        news=[],
    )
    assert "## Actualités récentes" in prompt.user
    assert "Aucune actualité récente trouvée" in prompt.user


def test_prompt_avec_erreur_news_demande_de_ne_pas_inventer():
    df = _prices()
    prompt = build_signal_prompt(
        _signal(df),
        df,
        symbol="AAPL",
        timeframe="1d",
        news=[],
        news_error="service indisponible",
    )
    assert "service indisponible" in prompt.user
    assert "N'en invente pas" in prompt.user
