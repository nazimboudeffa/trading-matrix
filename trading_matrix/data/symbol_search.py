"""Recherche de symboles pour l'autocomplétion du champ « Symbole ».

Deux niveaux :

1. **réseau** via ``yfinance.Search`` (rapide, exhaustif) ;
2. **local** via les listes de marchés déjà connues (``markets.search_local``).

Le module est indépendant de Qt : c'est l'interface qui l'exécute dans un
thread séparé.
"""

from __future__ import annotations

import logging
from collections import OrderedDict

import yfinance as yf

from trading_matrix.data.markets import Instrument, search_local

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = {"equity", "etf", "index", "crypto", "currency"}
_CACHE_MAX_ENTRIES = 100

# Places de cotation principales : une valeur qui y est listée passe devant une
# ligne secondaire ou un marché de gré à gré pour un même degré de pertinence.
_PREFERRED_EXCHANGES = (
    "paris",
    "xetra",
    "london",
    "lse",
    "milan",
    "borsa italiana",
    "amsterdam",
    "euronext",
    "nyse",
    "nasdaq",
    "swiss",
)
_SECONDARY_EXCHANGES = (
    "frankfurt",
    "stuttgart",
    "berlin",
    "dusseldorf",
    "hamburg",
    "hanover",
    "munich",
    "vienna",
    "brussels",
    "lisbon",
    "madrid",
    "toronto",
    "tsx",
    "asx",
)
_OTC_MARKERS = ("otc", "oqx", "pnk", "grey", "gray")

# Cache mémoire des dernières requêtes (borné, pour éviter de marteler Yahoo).
_CACHE: "OrderedDict[str, list[Instrument]]" = OrderedDict()


def search_symbols(query: str, limit: int = 12) -> list[Instrument]:
    """Retourne les symboles correspondant à ``query``.

    Ne lève pas d'exception : en cas d'échec réseau, repli sur l'univers local.
    """
    text = (query or "").strip()
    if len(text) < 2:
        return []

    key = text.lower()
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return cached[:limit]

    results = _search_network(text, limit=max(limit * 2, 12))
    if not results:
        results = search_local(text, limit=limit)

    results = _sort_results(_dedupe(results), text)
    if results:
        _CACHE[key] = results
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return results[:limit]


def _search_network(query: str, limit: int) -> list[Instrument]:
    try:
        quotes = yf.Search(query, max_results=limit, news_count=0).quotes or []
    except Exception as exc:
        logger.warning("Recherche yfinance indisponible : %s", exc)
        return []

    instruments: list[Instrument] = []
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        quote_type = str(quote.get("quoteType", "")).lower()
        if quote_type and quote_type not in _ALLOWED_TYPES:
            continue
        symbol = str(quote.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        name = quote.get("longname") or quote.get("shortname") or ""
        instruments.append(
            Instrument(
                symbol=symbol,
                name=str(name).strip(),
                exchange=str(quote.get("exchDisp") or "").strip(),
            )
        )
    return instruments


def _rank(instrument: Instrument, needle: str) -> int:
    symbol = instrument.symbol.lower()
    name = instrument.name.lower()
    if symbol == needle:
        return 0
    if symbol.startswith(needle):
        return 1
    if name.startswith(needle):
        return 2
    if needle in symbol:
        return 3
    if needle in name:
        return 4
    return 5


def _dedupe(instruments: list[Instrument]) -> list[Instrument]:
    best: dict[str, Instrument] = {}
    for instrument in instruments:
        current = best.get(instrument.symbol)
        if current is None or (not current.name and instrument.name):
            best[instrument.symbol] = instrument
    return list(best.values())


def _exchange_penalty(exchange: str) -> int:
    """Pénalité de classement selon la place de cotation (0 = principale)."""
    text = (exchange or "").strip().lower()
    if not text:
        return 2
    if any(marker in text for marker in _OTC_MARKERS):
        return 3
    if any(marker in text for marker in _PREFERRED_EXCHANGES):
        return 0
    if any(marker in text for marker in _SECONDARY_EXCHANGES):
        return 1
    return 2


def _sort_results(instruments: list[Instrument], query: str) -> list[Instrument]:
    needle = query.strip().lower()
    indexed = list(enumerate(instruments))
    indexed.sort(
        key=lambda item: (
            _rank(item[1], needle) + _exchange_penalty(item[1].exchange),
            _rank(item[1], needle),
            item[0],
        )
    )
    return [instrument for _, instrument in indexed]
