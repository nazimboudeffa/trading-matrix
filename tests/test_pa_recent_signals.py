"""Un Order Block apparu entre deux recalculs doit donner un signal récent."""

import numpy as np
import pandas as pd

from trading_matrix.strategies.base import StrategyContext
from user_strategies.price_action_general import PriceActionGeneral


def _ohlcv() -> pd.DataFrame:
    rows: list[tuple[float, float, float, float]] = []
    for k in range(25):
        o = 100 + 0.02 * k
        c = o + 0.04
        rows.append((o, c + 0.08, o - 0.08, c))

    # 25 : OB baissier, 26 : impulsion qui le confirme (mèche dans la zone),
    # 27-28 : repli au-dessus de la zone, 29 : pinbar haussière dans la zone.
    rows.extend(
        [
            (101.0, 101.2, 99.8, 100.0),
            (100.5, 104.0, 100.4, 103.5),
            (103.4, 103.6, 102.4, 103.0),
            (102.8, 103.0, 102.2, 102.4),
            (101.5, 102.2, 100.5, 102.0),
        ]
    )
    arr = np.asarray(rows, dtype=float)
    return pd.DataFrame(
        {"Open": arr[:, 0], "High": arr[:, 1], "Low": arr[:, 2], "Close": arr[:, 3]},
        index=pd.date_range("2024-01-01", periods=len(arr), freq="h"),
    )


def test_order_block_detected_between_cycles_yields_signal_on_last_bar() -> None:
    df = _ohlcv()

    signals = PriceActionGeneral().analyze(
        StrategyContext(df=df, params={"require_trend": False})
    )

    assert any(
        s.setup_type == "OB_REACTION_BULL" and s.time == df.index[-1]
        for s in signals
    )
