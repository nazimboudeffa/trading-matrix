import pandas as pd


def df_to_candles(df: pd.DataFrame):
    """Convertit DataFrame OHLCV en format pour pyqtgraph (x = index ordinal)"""
    # Retourne listes
    dates = df.index
    opens = df["Open"].values
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values
    volumes = df["Volume"].values if "Volume" in df.columns else None
    return dates, opens, highs, lows, closes, volumes
