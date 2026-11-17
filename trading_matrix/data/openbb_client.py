import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

try:
    from openbb import obb
    _HAS_OPENBB = True
except Exception as e:
    logging.warning(f"OpenBB not fully initialized: {e}")
    _HAS_OPENBB = False

try:
    import yfinance as yf
    _HAS_YF = True
except Exception as e:
    logging.warning(f"yfinance not available: {e}")
    _HAS_YF = False

from trading_matrix.data.demo import generate_demo

#: Nombre maximal d'actualités demandées par défaut.
NEWS_LIMIT = 5
#: Longueur maximale d'un extrait d'article injecté dans le prompt.
NEWS_SUMMARY_MAX = 180


@dataclass(frozen=True)
class NewsItem:
    """Une actualité normalisée, prête à être affichée ou injectée dans un prompt."""

    title: str
    publisher: str = ""
    published_at: datetime | None = None
    url: str = ""
    summary: str = ""


def _clean_text(value: object, max_length: int = 0) -> str:
    """Compacte les espaces et tronque proprement un texte."""
    text = " ".join(str(value or "").split())
    if max_length and len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def _as_datetime(value: object) -> datetime | None:
    """Convertit une date OpenBB/yfinance en datetime UTC (ou ``None``)."""
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number > 1e12:  # timestamp en millisecondes
            number /= 1000.0
        try:
            moment = datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        try:
            stamp = pd.to_datetime(value, utc=True, errors="coerce")
        except (TypeError, ValueError):
            return None
        if pd.isna(stamp):
            return None
        moment = stamp.to_pydatetime()

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _nested_url(value: object) -> str:
    """Extrait une URL d'un champ OpenBB/yfinance (dict ou chaîne)."""
    if isinstance(value, dict):
        for key in ("url", "href"):
            if value.get(key):
                return str(value[key])
        return ""
    return str(value or "") if isinstance(value, str) else ""


def _finalize_news(items: list[NewsItem], limit: int) -> list[NewsItem]:
    """Trie par date décroissante, déduplique et borne le nombre d'articles."""
    deduped: list[NewsItem] = []
    seen: set[str] = set()
    fallback = datetime.min.replace(tzinfo=timezone.utc)
    for item in sorted(
        items,
        key=lambda news: news.published_at or fallback,
        reverse=True,
    ):
        key = item.title.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _news_from_frame(df: pd.DataFrame, limit: int) -> list[NewsItem]:
    """Normalise le DataFrame renvoyé par ``obb.news.company``."""
    if df is None or getattr(df, "empty", True):
        return []

    columns = {str(column).strip().lower(): column for column in df.columns}

    def column(*names: str):
        for name in names:
            if name in columns:
                return columns[name]
        return None

    title_col = column("title", "headline")
    if title_col is None:
        return []
    publisher_col = column("publisher", "source", "provider")
    date_col = column("date", "published_at", "datetime", "time")
    summary_col = column("excerpt", "summary", "description")
    url_col = column("url", "link")

    items: list[NewsItem] = []
    for position, (_, row) in enumerate(df.iterrows()):
        title = _clean_text(row.get(title_col))
        if not title:
            continue
        published_at = _as_datetime(row.get(date_col)) if date_col is not None else None
        if published_at is None and isinstance(df.index, pd.DatetimeIndex):
            published_at = _as_datetime(df.index[position])
        items.append(
            NewsItem(
                title=title,
                publisher=_clean_text(row.get(publisher_col)) if publisher_col else "",
                published_at=published_at,
                url=_clean_text(row.get(url_col)) if url_col else "",
                summary=(
                    _clean_text(row.get(summary_col), NEWS_SUMMARY_MAX)
                    if summary_col
                    else ""
                ),
            )
        )
    return _finalize_news(items, limit)


def _news_from_yfinance(raw_items: object, limit: int) -> list[NewsItem]:
    """Normalise les actualités brutes de ``yfinance`` (ancien et nouveau format)."""
    items: list[NewsItem] = []
    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue

        content = raw.get("content")
        if isinstance(content, dict):
            title = content.get("title") or content.get("summary")
            summary = content.get("summary") or content.get("description") or ""
            provider = content.get("provider")
            publisher = provider.get("displayName") if isinstance(provider, dict) else ""
            published_at = content.get("pubDate") or content.get("displayTime")
            url = (
                _nested_url(content.get("clickThroughUrl"))
                or _nested_url(content.get("canonicalUrl"))
                or _nested_url(content.get("previewUrl"))
            )
        else:
            title = raw.get("title")
            summary = raw.get("summary") or raw.get("description") or ""
            publisher = raw.get("publisher") or raw.get("source") or ""
            published_at = raw.get("providerPublishTime") or raw.get("publishTime")
            url = raw.get("link") or raw.get("url") or ""

        cleaned_title = _clean_text(title)
        if not cleaned_title:
            continue
        items.append(
            NewsItem(
                title=cleaned_title,
                publisher=_clean_text(publisher),
                published_at=_as_datetime(published_at),
                url=_clean_text(url),
                summary=_clean_text(summary, NEWS_SUMMARY_MAX),
            )
        )
    return _finalize_news(items, limit)


class OpenBBClient:
    def __init__(self):
        self.obb = obb if _HAS_OPENBB else None

    def is_available(self) -> bool:
        return (_HAS_OPENBB and self.obb is not None) or _HAS_YF

    @staticmethod
    def _period_to_start(period: str) -> str | None:
        """Convertit une période type '6mo', '1y', '30d' en date de départ.

        OpenBB 5 ne prend plus ``period`` mais ``start_date``/``end_date``.
        """
        match = re.fullmatch(r"(\d+)\s*(d|wk|mo|y)", str(period).strip().lower())
        if not match:
            return None
        amount, unit = int(match.group(1)), match.group(2)
        days = {"d": 1, "wk": 7, "mo": 30, "y": 365}[unit] * amount
        return (date.today() - timedelta(days=days)).isoformat()

    def get_ohlcv(self, symbol: str, interval: str = "1d", period: str = "6mo", **kwargs) -> pd.DataFrame:
        """
        Récupère OHLCV.
        1) Tente OpenBB si disponible
        2) Sinon tente yfinance directement
        3) Sinon données de démo
        """
        # 1) Essayer OpenBB (différentes formes selon version)
        if _HAS_OPENBB and self.obb is not None:
            # OpenBB 5+ : les providers sont des namespaces racine (obb.yfinance.*)
            provider_ns = getattr(self.obb, "yfinance", None)
            if provider_ns is not None and hasattr(provider_ns, "equity") and hasattr(
                provider_ns.equity, "price"
            ):
                try:
                    kwargs_openbb = {
                        "symbol": symbol,
                        "interval": interval,
                        "provider": "yfinance",
                    }
                    start_date = self._period_to_start(period)
                    if start_date:
                        kwargs_openbb["start_date"] = start_date
                    res = provider_ns.equity.price.historical(**kwargs_openbb)
                    return self._normalize(res.to_df())
                except Exception as e:
                    logging.debug(f"OpenBB v5 attempt failed: {e}")

            try:
                # Forme OpenBB 4.x (obb.equity.price.historical)
                if hasattr(self.obb, "equity") and hasattr(self.obb.equity, "price"):
                    try:
                        res = self.obb.equity.price.historical(
                            symbol=symbol,
                            interval=interval,
                            period=period,
                            provider="yfinance",
                        )
                        df = res.to_df()
                        return self._normalize(df)
                    except Exception:
                        pass
                    try:
                        res = self.obb.equity.price.historical(symbol=symbol, interval=interval, period=period)
                        df = res.to_df()
                        return self._normalize(df)
                    except Exception:
                        pass
            except Exception as e:
                logging.debug(f"OpenBB attempt failed: {e}")

        # 2) yfinance direct
        if _HAS_YF:
            try:
                df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
                if df is not None and not df.empty:
                    return self._normalize_yf(df)
            except Exception as e:
                logging.warning(f"yfinance direct failed: {e}")

        # 3) Démo
        logging.warning("Using demo data")
        return generate_demo(symbol=symbol)

    def get_news(self, symbol: str, limit: int = NEWS_LIMIT, **kwargs) -> list[NewsItem]:
        """Récupère les dernières actualités d'un actif.

        Chaîne de récupération, cohérente avec celle des OHLCV :

        1. **OpenBB** (``obb.news.company``) si disponible ;
        2. **yfinance** directement (``yf.Search``), car le provider OpenBB
           repose sur Yahoo et peut échouer selon l'état du service ;
        3. liste vide si aucune source ne répond.

        Ne lève pas d'exception pour un actif sans actualité : le retour vide
        signifie « rien à ajouter au contexte ».
        """
        symbol = (symbol or "").strip()
        if not symbol:
            return []

        try:
            wanted = max(1, min(int(limit), 20))
        except (TypeError, ValueError):
            wanted = NEWS_LIMIT
        fetch_limit = max(wanted * 2, wanted)

        if _HAS_OPENBB and self.obb is not None:
            news_ns = getattr(self.obb, "news", None)
            company = getattr(news_ns, "company", None) if news_ns is not None else None
            if callable(company):
                # Provider installé d'abord, puis priorité configurée dans OpenBB.
                for provider in ("yfinance", None):
                    try:
                        request = {"symbol": symbol, "limit": fetch_limit, **kwargs}
                        if provider:
                            request["provider"] = provider
                        result = company(**request)
                        items = _news_from_frame(result.to_df(), wanted)
                        if items:
                            return items
                    except Exception as exc:  # noqa: BLE001 - repli silencieux
                        logging.debug("OpenBB news attempt failed (%s): %s", provider, exc)

        if _HAS_YF:
            try:
                search = yf.Search(symbol, max_results=1, news_count=fetch_limit, timeout=10)
                items = _news_from_yfinance(getattr(search, "news", None), wanted)
                if items:
                    return items
            except Exception as exc:  # noqa: BLE001 - aucune news = contexte vide
                logging.warning("yfinance news failed: %s", exc)

        return []

    def _normalize_yf(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Si MultiIndex (cas rare)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={c: str(c).title() for c in df.columns})
        # Forcer noms
        mapping = {}
        for c in df.columns:
            cl = c.lower()
            if cl == "open": mapping[c] = "Open"
            elif cl == "high": mapping[c] = "High"
            elif cl == "low": mapping[c] = "Low"
            elif cl == "close": mapping[c] = "Close"
            elif cl in ("adj close", "adjclose"): mapping[c] = "Adj Close"
            elif cl == "volume": mapping[c] = "Volume"
        df = df.rename(columns=mapping)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df.index.name = "Date"
        keep = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df.columns]
        if not all(k in keep for k in ["Open", "High", "Low", "Close"]):
            raise ValueError(f"Colonnes OHLC manquantes. Reçu: {df.columns.tolist()}")
        df = df[keep]
        df = df.dropna(how="any")
        return df

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            raise ValueError("Données vides reçues")

        df = df.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(-1)

        colmap = {}
        for c in df.columns:
            cl = str(c).lower().replace(" ", "")
            if cl == "open": colmap[c] = "Open"
            elif cl == "high": colmap[c] = "High"
            elif cl == "low": colmap[c] = "Low"
            elif cl == "close": colmap[c] = "Close"
            elif cl in ("adjclose", "adjustedclose"): colmap[c] = "Adj Close"
            elif cl == "volume": colmap[c] = "Volume"
        df = df.rename(columns=colmap)

        if not isinstance(df.index, pd.DatetimeIndex):
            for c in df.columns:
                cl = str(c).lower()
                if cl in ("date", "datetime", "time", "timestamp"):
                    try:
                        df[c] = pd.to_datetime(df[c])
                        df = df.set_index(c)
                        break
                    except Exception:
                        pass
            if not isinstance(df.index, pd.DatetimeIndex):
                try:
                    df.index = pd.to_datetime(df.index)
                except Exception:
                    pass

        df.index.name = "Date"
        keep = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df.columns]
        if not all(k in keep for k in ["Open", "High", "Low", "Close"]):
            raise ValueError(f"Colonnes OHLC manquantes. Reçu: {df.columns.tolist()}")
        df = df[keep]
        df = df.dropna(how="any")
        return df
