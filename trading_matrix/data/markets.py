"""Catalogue des marchés et récupération des constituants d'indices.

Le module est volontairement indépendant de Qt : il est utilisable en ligne de
commande et testable sans interface graphique.

Chaîne de récupération pour un marché :

1. cache disque (``cache/markets.json``) s'il a moins de ``CACHE_TTL_DAYS`` ;
2. sinon page Wikipédia, parsée via ``pandas.read_html`` ;
3. sinon cache périmé ;
4. sinon instantané embarqué (``market_seeds.json``).

Si aucune source ne répond, ``MarketDataError`` est levée avec un message clair.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from trading_matrix.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

CACHE_DIR = PROJECT_ROOT / "cache"
CACHE_FILE = CACHE_DIR / "markets.json"
SEEDS_FILE = Path(__file__).with_name("market_seeds.json")

CACHE_TTL_DAYS = 7
HTTP_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 TradingMatrix/0.1"
)

_SYMBOL_CLEAN_RE = re.compile(r"[^A-Z0-9.\-]")
_SYMBOL_VALID_RE = re.compile(r"^[A-Z0-9.\-]{1,15}$")
_TICKER_COLUMNS = ("ticker", "symbol", "code")
_NAME_COLUMNS = ("company", "security", "name")
_SECTOR_COLUMNS = (
    "sector",
    "gics sector",
    "gics sub-industry",
    "icb sector",
    "icb industry",
    "prime standard sector",
    "ftse industry",
)


class MarketDataError(RuntimeError):
    """Aucune source (réseau, cache, seeds) n'a pu fournir les données."""


@dataclass(frozen=True)
class Market:
    """Description d'un marché (indice) et de sa source."""

    id: str
    label: str
    source_url: str
    suffix: str = ""
    table_index: int | None = None
    expected_rows: int | None = None


@dataclass(frozen=True)
class Instrument:
    """Un titre négociable, tel qu'affiché dans l'interface."""

    symbol: str
    name: str = ""
    exchange: str = ""
    sector: str = ""
    market: str = ""


@dataclass(frozen=True)
class MarketSnapshot:
    """Résultat d'un chargement de marché, avec sa provenance."""

    market: Market
    instruments: list[Instrument] = field(default_factory=list)
    source: str = ""  # "network" | "cache" | "seeds"
    updated_at: datetime | None = None


MARKETS: tuple[Market, ...] = (
    Market(
        "cac40",
        "CAC 40",
        "https://en.wikipedia.org/wiki/CAC_40",
        suffix=".PA",
        table_index=4,
        expected_rows=40,
    ),
    Market(
        "dax",
        "DAX 40",
        "https://en.wikipedia.org/wiki/DAX",
        suffix=".DE",
        table_index=4,
        expected_rows=40,
    ),
    Market(
        "ftse_mib",
        "FTSE MIB",
        "https://en.wikipedia.org/wiki/FTSE_MIB",
        suffix=".MI",
        table_index=2,
        expected_rows=40,
    ),
    Market(
        "ftse100",
        "FTSE 100",
        "https://en.wikipedia.org/wiki/FTSE_100_Index",
        suffix=".L",
        table_index=6,
        expected_rows=100,
    ),
    Market(
        "eurostoxx50",
        "Euro Stoxx 50",
        "https://en.wikipedia.org/wiki/EURO_STOXX_50",
        table_index=3,
        expected_rows=50,
    ),
    Market(
        "sp500",
        "S&P 500",
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        table_index=0,
        expected_rows=503,
    ),
    Market(
        "nasdaq100",
        "Nasdaq 100",
        "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies",
        table_index=0,
        expected_rows=101,
    ),
)


def list_markets() -> tuple[Market, ...]:
    """Retourne les marchés disponibles, dans l'ordre d'affichage."""
    return MARKETS


def get_market(market_id: str) -> Market:
    """Retourne un marché par son identifiant, sinon ``KeyError``."""
    for market in MARKETS:
        if market.id == market_id:
            return market
    raise KeyError(f"Marché inconnu : {market_id}")


# ---------------------------------------------------------------------------
# Parsing de la page Wikipédia
# ---------------------------------------------------------------------------

def _normalize_column(name: object) -> str:
    """Nettoie un nom de colonne : minuscules, sans notes de bas de page."""
    return re.sub(r"\[\d+\]", "", str(name)).strip().lower()


def _pick_column(columns, candidates: tuple[str, ...]) -> object | None:
    """Trouve une colonne par correspondance exacte puis par préfixe."""
    normalized = {col: _normalize_column(col) for col in columns}
    for candidate in candidates:
        for col, name in normalized.items():
            if name == candidate:
                return col
    for candidate in candidates:
        for col, name in normalized.items():
            if name.startswith(candidate):
                return col
    return None


def _normalize_symbol(raw: object, suffix: str) -> str:
    """Normalise un ticker et applique le suffixe de place si nécessaire."""
    text = str(raw).strip().upper().replace(" ", "")
    text = _SYMBOL_CLEAN_RE.sub("", text)
    if not text or text == "NAN" or not any(ch.isalpha() for ch in text):
        return ""
    if not _SYMBOL_VALID_RE.match(text):
        return ""
    if suffix and "." not in text:
        text = f"{text}{suffix}"
    return text


def _clean_text(value: object) -> str:
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def _extract_instruments(table: pd.DataFrame, market: Market) -> list[Instrument]:
    ticker_col = _pick_column(table.columns, _TICKER_COLUMNS)
    if ticker_col is None:
        return []
    name_col = _pick_column(table.columns, _NAME_COLUMNS)
    sector_col = _pick_column(table.columns, _SECTOR_COLUMNS)

    instruments: list[Instrument] = []
    seen: set[str] = set()
    for _, row in table.iterrows():
        symbol = _normalize_symbol(row[ticker_col], market.suffix)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        instruments.append(
            Instrument(
                symbol=symbol,
                name=_clean_text(row[name_col]) if name_col is not None else "",
                exchange=market.label,
                sector=_clean_text(row[sector_col]) if sector_col is not None else "",
                market=market.label,
            )
        )
    return instruments


def _find_table(tables: list[pd.DataFrame], market: Market) -> pd.DataFrame | None:
    """Sélectionne la table des constituants, sans dépendre d'un index figé."""
    if market.table_index is not None and 0 <= market.table_index < len(tables):
        hinted = tables[market.table_index]
        if _pick_column(hinted.columns, _TICKER_COLUMNS) is not None:
            return hinted

    candidates = [
        table
        for table in tables
        if _pick_column(table.columns, _TICKER_COLUMNS) is not None
        and 10 <= len(table) <= 1000
    ]
    if not candidates:
        return None
    if market.expected_rows:
        candidates.sort(key=lambda table: abs(len(table) - market.expected_rows))
    else:
        candidates.sort(key=len, reverse=True)
    return candidates[0]


def parse_market_page(html: str, market: Market) -> list[Instrument]:
    """Extrait les constituants depuis le HTML d'une page (testable hors ligne)."""
    tables = pd.read_html(StringIO(html))
    table = _find_table(tables, market)
    if table is None:
        raise MarketDataError(f"{market.label} : table des constituants introuvable")
    instruments = _extract_instruments(table, market)
    if not instruments:
        raise MarketDataError(f"{market.label} : aucun symbole exploitable dans la table")
    return instruments


# ---------------------------------------------------------------------------
# Cache disque
# ---------------------------------------------------------------------------

def _read_cache() -> dict:
    try:
        if not CACHE_FILE.exists():
            return {}
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # cache corrompu : on l'ignore
        logger.warning("Cache marchés illisible (%s), il sera reconstruit", exc)
        return {}


def _write_cache(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CACHE_FILE)


def _rows_to_instruments(rows: list[dict]) -> list[Instrument]:
    instruments = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        instruments.append(
            Instrument(
                symbol=str(row.get("symbol", "")),
                name=str(row.get("name", "")),
                exchange=str(row.get("exchange", "")),
                sector=str(row.get("sector", "")),
                market=str(row.get("market", "")),
            )
        )
    return instruments


def _cache_entry(market_id: str, max_age_days: int | None = CACHE_TTL_DAYS):
    """Retourne (rows, updated_at) du cache, ou None s'il est absent/trop vieux."""
    entry = _read_cache().get("markets", {}).get(market_id)
    if not isinstance(entry, dict):
        return None
    try:
        updated_at = datetime.fromisoformat(str(entry.get("updated_at", "")))
    except ValueError:
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if max_age_days is not None:
        if datetime.now(timezone.utc) - updated_at > timedelta(days=max_age_days):
            return None
    rows = entry.get("instruments")
    if not isinstance(rows, list) or not rows:
        return None
    return rows, updated_at


def _store_in_cache(market: Market, instruments: list[Instrument]) -> datetime:
    now = datetime.now(timezone.utc)
    data = _read_cache()
    markets = data.setdefault("markets", {})
    markets[market.id] = {
        "label": market.label,
        "updated_at": now.isoformat(),
        "instruments": [asdict(instrument) for instrument in instruments],
    }
    _write_cache(data)
    return now


# ---------------------------------------------------------------------------
# Instantané embarqué (secours hors ligne)
# ---------------------------------------------------------------------------

def _read_seeds_file() -> dict:
    try:
        if not SEEDS_FILE.exists():
            return {}
        data = json.loads(SEEDS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Seeds marchés illisibles (%s)", exc)
        return {}


def load_seeds(market_id: str) -> list[Instrument]:
    """Retourne les constituants embarqués d'un marché (liste vide si absent)."""
    rows = _read_seeds_file().get("markets", {}).get(market_id)
    return _rows_to_instruments(rows) if isinstance(rows, list) else []


def dump_seeds(path: Path | None = None) -> Path:
    """Régénère ``market_seeds.json`` depuis le réseau (maintenance manuelle)."""
    target = path or SEEDS_FILE
    payload: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "markets": {},
    }
    for market in MARKETS:
        try:
            instruments = _fetch_from_network(market)
        except Exception as exc:
            logger.warning("%s : seeds non générées (%s)", market.label, exc)
            continue
        payload["markets"][market.id] = [asdict(instrument) for instrument in instruments]
        print(f"{market.label:14} {len(instruments):4} symboles")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------

def _fetch_from_network(market: Market) -> list[Instrument]:
    response = requests.get(
        market.source_url,
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return parse_market_page(response.text, market)


def fetch_market(market_id: str, force: bool = False) -> MarketSnapshot:
    """Charge un marché : cache frais, réseau, cache périmé, puis seeds."""
    market = get_market(market_id)

    if not force:
        cached = _cache_entry(market.id)
        if cached is not None:
            rows, updated_at = cached
            return MarketSnapshot(market, _rows_to_instruments(rows), "cache", updated_at)

    try:
        instruments = _fetch_from_network(market)
        updated_at = _store_in_cache(market, instruments)
        logger.info("%s : %d symboles depuis le réseau", market.label, len(instruments))
        return MarketSnapshot(market, instruments, "network", updated_at)
    except Exception as exc:
        logger.warning("%s : réseau indisponible (%s)", market.label, exc)

    stale = _cache_entry(market.id, max_age_days=None)
    if stale is not None:
        rows, updated_at = stale
        return MarketSnapshot(market, _rows_to_instruments(rows), "cache", updated_at)

    seeds = load_seeds(market.id)
    if seeds:
        return MarketSnapshot(market, seeds, "seeds", None)

    raise MarketDataError(
        f"{market.label} : impossible de récupérer les constituants "
        "(réseau, cache et données embarquées indisponibles)"
    )


def local_universe() -> list[Instrument]:
    """Univers local (seeds + cache) pour la recherche hors ligne."""
    instruments: list[Instrument] = []
    seen: set[str] = set()

    seeds = _read_seeds_file().get("markets", {})
    if isinstance(seeds, dict):
        for rows in seeds.values():
            for instrument in _rows_to_instruments(rows if isinstance(rows, list) else []):
                if instrument.symbol not in seen:
                    seen.add(instrument.symbol)
                    instruments.append(instrument)

    cache = _read_cache().get("markets", {})
    if isinstance(cache, dict):
        for entry in cache.values():
            rows = entry.get("instruments") if isinstance(entry, dict) else None
            for instrument in _rows_to_instruments(rows if isinstance(rows, list) else []):
                if instrument.symbol not in seen:
                    seen.add(instrument.symbol)
                    instruments.append(instrument)

    return instruments


def search_local(query: str, limit: int = 12) -> list[Instrument]:
    """Recherche par sous-chaîne dans l'univers local (hors ligne)."""
    needle = query.strip().lower()
    if len(needle) < 2:
        return []

    def rank(instrument: Instrument) -> int:
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

    matches = [
        instrument
        for instrument in local_universe()
        if needle in instrument.symbol.lower() or needle in instrument.name.lower()
    ]
    matches.sort(key=rank)
    return matches[:limit]
