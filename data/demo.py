import zlib

import numpy as np
import pandas as pd


def generate_demo(symbol: str = "DEMO", days: int = 200) -> pd.DataFrame:
    np.random.seed(zlib.crc32(symbol.encode("utf-8")) % (2**32))
    dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq="D")
    price = 100.0
    data = []
    for _ in dates:
        open_p = price
        close_p = open_p + np.random.normal(0, 2)
        high_p = max(open_p, close_p) + abs(np.random.normal(0, 1))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, 1))
        volume = int(np.random.lognormal(14, 0.5))
        data.append((open_p, high_p, low_p, close_p, volume))
        price = close_p
    df = pd.DataFrame(data, columns=["Open", "High", "Low", "Close", "Volume"], index=dates)
    return df
