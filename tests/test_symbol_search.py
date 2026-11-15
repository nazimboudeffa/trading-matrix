"""Tests de la recherche de symboles (réseau simulé, aucun accès Internet)."""

from __future__ import annotations

import pytest

from trading_matrix.data import symbol_search
from trading_matrix.data.markets import Instrument


class FakeSearch:
    """Remplace ``yfinance.Search`` : réponses figées et appels comptés."""

    calls: list[str] = []
    quotes_by_query: dict[str, list[dict]] = {}

    def __init__(self, query: str, max_results: int = 8, news_count: int = 0):
        type(self).calls.append(query)
        self._query = query

    @property
    def quotes(self) -> list[dict]:
        return [dict(quote) for quote in type(self).quotes_by_query.get(self._query, [])]


def quote(symbol: str, name: str = "", exchange: str = "", quote_type: str = "EQUITY") -> dict:
    return {
        "symbol": symbol,
        "longname": name,
        "exchDisp": exchange,
        "quoteType": quote_type,
    }


@pytest.fixture
def fake_search(monkeypatch):
    FakeSearch.calls = []
    FakeSearch.quotes_by_query = {}
    monkeypatch.setattr(symbol_search.yf, "Search", FakeSearch)
    return FakeSearch


@pytest.fixture(autouse=True)
def clear_memory_cache():
    symbol_search._CACHE.clear()
    yield
    symbol_search._CACHE.clear()


def test_primary_exchange_ranked_before_otc(fake_search):
    fake_search.quotes_by_query["lvmh"] = [
        quote("LVMHF", "LVMH", "OTC Markets"),
        quote("MC.PA", "LVMH", "Paris"),
        quote("MOH1.F", "LVMH", "Frankfurt"),
    ]

    results = symbol_search.search_symbols("lvmh", limit=5)
    assert [instrument.symbol for instrument in results] == ["MC.PA", "MOH1.F", "LVMHF"]
    assert fake_search.calls == ["lvmh"]


def test_exact_symbol_ranked_first(fake_search):
    fake_search.quotes_by_query["III"] = [
        quote("III.L", "3i Group", "London"),
        quote("GIII", "G-III Apparel Group", "NASDAQ"),
        quote("III", "Information Services Group", "NASDAQ"),
    ]

    results = symbol_search.search_symbols("III", limit=5)
    assert [instrument.symbol for instrument in results] == ["III", "III.L", "GIII"]


def test_unknown_quote_types_are_filtered(fake_search):
    fake_search.quotes_by_query["fonds"] = [
        quote("FONDX", "Fonds X", "Paris", quote_type="MUTUALFUND"),
        quote("ETF.PA", "ETF Y", "Paris", quote_type="ETF"),
        quote("AIR.PA", "Airbus", "Paris"),
    ]

    results = symbol_search.search_symbols("fonds", limit=5)
    assert [instrument.symbol for instrument in results] == ["ETF.PA", "AIR.PA"]


def test_duplicate_symbols_keep_the_named_listing(fake_search):
    fake_search.quotes_by_query["air"] = [
        quote("AIR.PA", "", "Paris"),
        quote("AIR.PA", "Airbus SE", "Paris"),
    ]

    results = symbol_search.search_symbols("air", limit=5)
    assert len(results) == 1
    assert results[0].symbol == "AIR.PA"
    assert results[0].name == "Airbus SE"


def test_short_query_does_not_call_network(fake_search):
    assert symbol_search.search_symbols(" a ") == []
    assert fake_search.calls == []


def test_results_are_cached_per_query(fake_search):
    fake_search.quotes_by_query["airbus"] = [quote("AIR.PA", "Airbus SE", "Paris")]

    symbol_search.search_symbols("airbus")
    symbol_search.search_symbols("airbus")
    assert fake_search.calls == ["airbus"]


def test_network_failure_falls_back_to_local(monkeypatch):
    class FailingSearch:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("réseau simulé indisponible")

    monkeypatch.setattr(symbol_search.yf, "Search", FailingSearch)
    monkeypatch.setattr(
        symbol_search,
        "search_local",
        lambda query, limit=12: [Instrument("AIR.PA", "Airbus", "CAC 40")],
    )

    results = symbol_search.search_symbols("airbus")
    assert [instrument.symbol for instrument in results] == ["AIR.PA"]


def test_empty_network_results_fall_back_to_local(fake_search, monkeypatch):
    fake_search.quotes_by_query["adidas"] = []
    monkeypatch.setattr(
        symbol_search,
        "search_local",
        lambda query, limit=12: [Instrument("ADS.DE", "Adidas", "DAX 40")],
    )

    results = symbol_search.search_symbols("adidas")
    assert [instrument.symbol for instrument in results] == ["ADS.DE"]


def test_limit_is_respected(fake_search):
    fake_search.quotes_by_query["total"] = [
        quote("TTE", "TotalEnergies", "NYSE"),
        quote("TTE.PA", "TotalEnergies", "Paris"),
        quote("TOTF.PA", "TotalEnergies", "Paris"),
    ]

    results = symbol_search.search_symbols("total", limit=2)
    assert len(results) == 2
    assert results[0].symbol == "TTE"


def test_exchange_penalties_are_ordered():
    instruments = [
        Instrument("OTC", "Foo Corp", "OTC Markets"),
        Instrument("UNK", "Foo Corp", "Nowhere"),
        Instrument("FRA", "Foo Corp", "Frankfurt"),
        Instrument("PAR", "Foo Corp", "Paris"),
    ]

    ordered = symbol_search._sort_results(instruments, "foo")
    assert [instrument.symbol for instrument in ordered] == ["PAR", "FRA", "UNK", "OTC"]
    assert symbol_search._exchange_penalty("") == 2
    assert symbol_search._exchange_penalty("OQX") == 3
    assert symbol_search._exchange_penalty("NasdaqGS") == 0
