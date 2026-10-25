import pandas as pd
import numpy as np

try:
    import ta
    _HAS_TA = True
except Exception:
    _HAS_TA = False


class IndicatorManager:
    @staticmethod
    def sma(df: pd.DataFrame, period: int = 20, column: str = "Close") -> pd.Series:
        return df[column].rolling(window=period).mean()

    @staticmethod
    def ema(df: pd.DataFrame, period: int = 20, column: str = "Close") -> pd.Series:
        return df[column].ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14, column: str = "Close") -> pd.Series:
        if _HAS_TA:
            try:
                return ta.momentum.RSIIndicator(close=df[column], window=period).rsi()
            except Exception:
                pass
        delta = df[column].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = "Close"):
        if _HAS_TA:
            try:
                m = ta.trend.MACD(close=df[column], window_slow=slow, window_fast=fast, window_sign=signal)
                return m.macd(), m.macd_signal(), m.macd_diff()
            except Exception:
                pass
        ema_fast = df[column].ewm(span=fast, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return macd_line, signal_line, hist

    @staticmethod
    def bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0, column: str = "Close"):
        if _HAS_TA:
            try:
                b = ta.volatility.BollingerBands(close=df[column], window=period, window_dev=std)
                return b.bollinger_hband(), b.bollinger_mavg(), b.bollinger_lband()
            except Exception:
                pass
        ma = df[column].rolling(window=period).mean()
        sd = df[column].rolling(window=period).std()
        upper = ma + std * sd
        lower = ma - std * sd
        return upper, ma, lower
