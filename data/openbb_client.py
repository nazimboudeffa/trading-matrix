import logging

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

from data.demo import generate_demo


class OpenBBClient:
    def __init__(self):
        self.obb = obb if _HAS_OPENBB else None

    def is_available(self) -> bool:
        return (_HAS_OPENBB and self.obb is not None) or _HAS_YF

    def get_ohlcv(self, symbol: str, interval: str = "1d", period: str = "6mo", **kwargs) -> pd.DataFrame:
        """
        Récupère OHLCV.
        1) Tente OpenBB si disponible
        2) Sinon tente yfinance directement
        3) Sinon données de démo
        """
        # 1) Essayer OpenBB (différentes formes selon version)
        if _HAS_OPENBB and self.obb is not None:
            try:
                # Forme courante
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
