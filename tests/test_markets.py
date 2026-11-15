"""Tests de la couche données « marchés » (aucun accès réseau)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from trading_matrix.data import markets
from trading_matrix.data.markets import Instrument, Market, MarketDataError

FIXTURE = Path(__file__).parent / "fixtures" / "market_sample.html"


def _test_market(**overrides) -> Market:
    params = {
        "id": "test",
        "label": "Test Index",
        "source_url": "https://example.invalid",
        "suffix": ".PA",
        "table_index": None,
        "expected_rows": 11,
    }
    params.update(overrides)
    return Market(**params)


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Isole le cache et les seeds dans un dossier temporaire."""
    cache_dir = tmp_path / "cache"
    cache_file = cache_dir / "markets.json"
    seeds_file = tmp_path / "market_seeds.json"
    monkeypatch.setattr(markets, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(markets, "CACHE_FILE", cache_file)
    monkeypatch.setattr(markets, "SEEDS_FILE", seeds_file)
    return cache_file, seeds_file


def _write_cache(
    cache_file: Path,
    market_id: str,
    updated_at: datetime,
    symbols=("AIR.PA",),
    names: dict[str, str] | None = None,
) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "label": market_id,
        "updated_at": updated_at.isoformat(),
        "instruments": [
            {
                "symbol": symbol,
                "name": (names or {}).get(symbol, f"Nom {symbol}"),
                "exchange": "Test",
                "sector": "",
                "market": market_id,
            }
            for symbol in symbols
        ],
    }
    cache_file.write_text(json.dumps({"markets": {market_id: entry}}), encoding="utf-8")


def _write_seeds(
    seeds_file: Path,
    market_id: str,
    symbols=("AIR.PA",),
    names: dict[str, str] | None = None,
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "markets": {
            market_id: [
                {
                    "symbol": symbol,
                    "name": (names or {}).get(symbol, f"Nom {symbol}"),
                    "exchange": "Embarqué",
                    "sector": "",
                    "market": market_id,
                }
                for symbol in symbols
            ]
        },
    }
    seeds_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- parsing

def test_normalize_symbol_adds_suffix_only_without_dot():
    assert markets._normalize_symbol("AIR", ".PA") == "AIR.PA"
    assert markets._normalize_symbol(" air ", ".PA") == "AIR.PA"
    assert markets._normalize_symbol("MC.PA", ".PA") == "MC.PA"
    assert markets._normalize_symbol("BT.A", ".L") == "BT.A"
    assert markets._normalize_symbol("BRK B", "") == "BRKB"
    assert markets._normalize_symbol("nan", "") == ""
    assert markets._normalize_symbol("—", ".PA") == ""
    assert markets._normalize_symbol("", ".PA") == ""


def test_pick_column_detects_ticker_despite_footnotes():
    columns = ["Company", "Ticker[1]", "GICS Sector"]
    frame = pd.DataFrame(columns=columns)
    assert markets._pick_column(frame.columns, markets._TICKER_COLUMNS) == "Ticker[1]"
    assert markets._pick_column(frame.columns, markets._NAME_COLUMNS) == "Company"
    assert markets._pick_column(frame.columns, markets._SECTOR_COLUMNS) == "GICS Sector"
    assert markets._pick_column(pd.DataFrame(columns=["A", "B"]).columns, markets._TICKER_COLUMNS) is None


def test_parse_market_page_detects_table_and_normalizes():
    html = FIXTURE.read_text(encoding="utf-8")
    instruments = markets.parse_market_page(html, _test_market())

    symbols = [instrument.symbol for instrument in instruments]
    assert len(instruments) == 11
    assert symbols[0] == "AIR.PA"
    assert "MC.PA" in symbols
    assert "MC.PA.PA" not in symbols
    assert len(symbols) == len(set(symbols))
    assert all(instrument.exchange == "Test Index" for instrument in instruments)

    by_symbol = {instrument.symbol: instrument for instrument in instruments}
    assert by_symbol["AIR.PA"].name == "Airbus"
    assert by_symbol["AIR.PA"].sector == "Industrials"


def test_parse_market_page_uses_hint_then_falls_back():
    html = FIXTURE.read_text(encoding="utf-8")

    hinted = markets.parse_market_page(html, _test_market(table_index=1))
    assert len(hinted) == 11

    # l'indice 0 pointe sur la table d'historique : la détection doit basculer
    fallback = markets.parse_market_page(html, _test_market(table_index=0, expected_rows=None))
    assert len(fallback) == 11


def test_parse_market_page_raises_without_constituents():
    html = (
        "<table><tr><th>Année</th><th>Revenu</th></tr>"
        "<tr><td>2024</td><td>10</td></tr></table>"
    )
    with pytest.raises(MarketDataError):
        markets.parse_market_page(html, _test_market(table_index=0))


# --------------------------------------------------------------------------- cache

def test_cache_entry_respects_ttl(isolated_storage):
    cache_file, _ = isolated_storage
    _write_cache(cache_file, "cac40", datetime.now(timezone.utc))
    assert markets._cache_entry("cac40") is not None

    # horodatage vieux de 5 s : TTL nul -> ignoré, mais utilisable en secours
    _write_cache(cache_file, "cac40", datetime.now(timezone.utc) - timedelta(seconds=5))
    assert markets._cache_entry("cac40", max_age_days=0) is None
    assert markets._cache_entry("cac40", max_age_days=None) is not None

    _write_cache(cache_file, "cac40", datetime.now(timezone.utc) - timedelta(days=10))
    assert markets._cache_entry("cac40") is None
    stale = markets._cache_entry("cac40", max_age_days=None)
    assert stale is not None


def test_cache_entry_ignores_corrupted_file(isolated_storage):
    cache_file, _ = isolated_storage
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{pas du json", encoding="utf-8")
    assert markets._cache_entry("cac40") is None


# --------------------------------------------------------------------------- chargement

def test_fetch_market_uses_fresh_cache_without_network(isolated_storage, monkeypatch):
    cache_file, _ = isolated_storage
    _write_cache(cache_file, "cac40", datetime.now(timezone.utc))

    def boom(market):
        raise AssertionError("le réseau ne doit pas être appelé avec un cache frais")

    monkeypatch.setattr(markets, "_fetch_from_network", boom)
    snapshot = markets.fetch_market("cac40")
    assert snapshot.source == "cache"
    assert [instrument.symbol for instrument in snapshot.instruments] == ["AIR.PA"]
    assert snapshot.updated_at is not None


def test_fetch_market_network_then_writes_cache(isolated_storage, monkeypatch):
    cache_file, _ = isolated_storage

    def fake_network(market):
        return [Instrument("AIR.PA", "Airbus", "Paris", "Industrials", market.label)]

    monkeypatch.setattr(markets, "_fetch_from_network", fake_network)
    snapshot = markets.fetch_market("cac40", force=True)

    assert snapshot.source == "network"
    assert snapshot.instruments[0].name == "Airbus"
    assert cache_file.exists()
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert payload["markets"]["cac40"]["instruments"][0]["symbol"] == "AIR.PA"


def test_fetch_market_falls_back_to_stale_cache(isolated_storage, monkeypatch):
    cache_file, _ = isolated_storage
    _write_cache(cache_file, "cac40", datetime.now(timezone.utc) - timedelta(days=30))

    def boom(market):
        raise RuntimeError("réseau simulé indisponible")

    monkeypatch.setattr(markets, "_fetch_from_network", boom)
    snapshot = markets.fetch_market("cac40", force=True)
    assert snapshot.source == "cache"
    assert len(snapshot.instruments) == 1


def test_fetch_market_falls_back_to_seeds(isolated_storage, monkeypatch):
    _, seeds_file = isolated_storage
    _write_seeds(seeds_file, "cac40", symbols=("AIR.PA", "MC.PA"))

    def boom(market):
        raise RuntimeError("réseau simulé indisponible")

    monkeypatch.setattr(markets, "_fetch_from_network", boom)
    snapshot = markets.fetch_market("cac40", force=True)
    assert snapshot.source == "seeds"
    assert [instrument.symbol for instrument in snapshot.instruments] == ["AIR.PA", "MC.PA"]
    assert snapshot.updated_at is None


def test_fetch_market_raises_when_no_source(isolated_storage, monkeypatch):
    _, seeds_file = isolated_storage
    _write_seeds(seeds_file, "cac40")  # aucune entrée pour dax

    def boom(market):
        raise RuntimeError("réseau simulé indisponible")

    monkeypatch.setattr(markets, "_fetch_from_network", boom)
    with pytest.raises(MarketDataError):
        markets.fetch_market("dax", force=True)


def test_force_bypasses_fresh_cache(isolated_storage, monkeypatch):
    cache_file, _ = isolated_storage
    _write_cache(cache_file, "cac40", datetime.now(timezone.utc), symbols=("OLD.PA",))
    calls: list[str] = []

    def fake_network(market):
        calls.append(market.id)
        return [Instrument("NEW.PA", "Nouveau", "Paris", "", market.label)]

    monkeypatch.setattr(markets, "_fetch_from_network", fake_network)
    snapshot = markets.fetch_market("cac40", force=True)

    assert calls == ["cac40"]
    assert snapshot.source == "network"
    assert snapshot.instruments[0].symbol == "NEW.PA"


# --------------------------------------------------------------------------- univers local

def test_local_universe_deduplicates_and_searches(isolated_storage):
    cache_file, seeds_file = isolated_storage
    names = {
        "AIR.PA": "Airbus",
        "AI.PA": "Air Liquide",
        "MC.PA": "LVMH",
        "TTE.PA": "TotalEnergies",
    }
    _write_seeds(seeds_file, "cac40", symbols=("AIR.PA", "AI.PA", "MC.PA"), names=names)
    _write_cache(
        cache_file,
        "cac40",
        datetime.now(timezone.utc),
        symbols=("AIR.PA", "TTE.PA"),
        names=names,
    )

    universe = markets.local_universe()
    symbols = [instrument.symbol for instrument in universe]
    assert len(symbols) == len(set(symbols))  # pas de doublons
    for expected in ("AIR.PA", "AI.PA", "MC.PA", "TTE.PA"):
        assert expected in symbols

    results = markets.search_local("air", limit=5)
    assert [instrument.symbol for instrument in results] == ["AIR.PA", "AI.PA"]
    assert markets.search_local("lvmh", limit=5)[0].symbol == "MC.PA"
    assert markets.search_local("a") == []
    assert markets.search_local("introuvable") == []


# --------------------------------------------------------------------------- forex

def test_forex_markets_are_static_and_offline(isolated_storage, monkeypatch):
    def boom(market):
        raise AssertionError("un marché statique ne doit pas appeler le réseau")

    monkeypatch.setattr(markets, "_fetch_from_network", boom)

    snapshot = markets.fetch_market("forex_majors")
    assert snapshot.source == "static"
    symbols = [instrument.symbol for instrument in snapshot.instruments]
    assert "EURUSD=X" in symbols
    assert all(instrument.exchange == "Forex" for instrument in snapshot.instruments)

    # Les paires forex sont recherchables hors ligne.
    assert markets.search_local("eurusd")[0].symbol == "EURUSD=X"


def test_forex_groups_cover_majors_minors_exotics():
    ids = {market.id for market in markets.list_markets()}
    assert {"forex_majors", "forex_minors", "forex_exotics"} <= ids
    assert all(market.category == "Forex" for market in markets.FOREX_MARKETS)

    majors = markets.get_market("forex_majors")
    assert len(majors.static_instruments) == 7
