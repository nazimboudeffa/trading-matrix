"""Tests de normalisation des actualités (aucun accès réseau)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from trading_matrix.data import openbb_client


def test_news_from_frame_normalise_colonnes_openbb():
    frame = pd.DataFrame(
        {
            "date": ["2026-11-16T10:00:00Z"],
            "title": ["  Titre   principal  "],
            "excerpt": ["Un résumé court."],
            "publisher": ["Les Échos"],
            "url": ["https://example.invalid/article"],
        }
    )

    items = openbb_client._news_from_frame(frame, 5)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Titre principal"
    assert item.publisher == "Les Échos"
    assert item.summary == "Un résumé court."
    assert item.url == "https://example.invalid/article"
    assert item.published_at == datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)


def test_news_from_frame_trie_et_limite():
    frame = pd.DataFrame(
        {
            "date": [
                "2026-11-15T10:00:00Z",
                "2026-11-16T10:00:00Z",
                "2026-11-16T10:00:00Z",
            ],
            "title": ["Ancienne", "Récente", "Doublon récent"],
            "publisher": ["A", "B", "C"],
        }
    )

    items = openbb_client._news_from_frame(frame, 1)

    assert [item.title for item in items] == ["Récente"]


def test_news_from_yfinance_gere_ancien_et_nouveau_format():
    epoch = int(datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc).timestamp())
    raw = [
        {
            "title": "Ancien format",
            "publisher": "Reuters",
            "link": "https://example.invalid/old",
            "providerPublishTime": epoch,
        },
        {
            "content": {
                "title": "Nouveau format",
                "summary": "Résumé du nouvel article.",
                "pubDate": "2026-11-16T12:00:00Z",
                "provider": {"displayName": "Bloomberg"},
                "canonicalUrl": {"url": "https://example.invalid/new"},
            }
        },
    ]

    items = openbb_client._news_from_yfinance(raw, 5)

    assert [item.title for item in items] == ["Nouveau format", "Ancien format"]
    assert items[0].publisher == "Bloomberg"
    assert items[0].url == "https://example.invalid/new"
    assert items[0].published_at == datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    assert items[1].publisher == "Reuters"


def test_news_from_yfinance_ignore_entrees_invalides():
    assert openbb_client._news_from_yfinance([None, {}, {"title": "  "}], 5) == []
