# Indicateurs personnalisés

Crée tes propres indicateurs dans ce dossier. Chaque fichier `.py` doit exposer une fonction `compute(df, **params)`.

## Structure minimale

```python
import pandas as pd
import numpy as np

NAME = "Mon indicateur"
DESCRIPTION = "Description courte"
PARAMS = {"period": 20}

def compute(df: pd.DataFrame, period: int = 20):
    from indicators.base import IndicatorResult, PlotItem
    ma = df["Close"].rolling(period).mean()
    return IndicatorResult(
        name=f"SMA perso ({period})",
        kind="overlay",  # "overlay" sur le graphique prix ou "subplot" en dessous
        plots=[PlotItem(label="MA", series=ma, color="#f0b90b", width=2)],
    )
```

## Astuces
- `df` contient `Open`, `High`, `Low`, `Close`, `Volume` avec index datetime
- `kind="overlay"` s'affiche directement sur les bougies
- `kind="subplot"` crée un panneau séparé
- Tu peux importer `ta`, `numpy`, `pandas`
- Tu peux ajouter `hlines=[(70,"#ef5350"), (30,"#26a69a")]`
- Recharge via "Rafraîchir" dans le panneau "Mes indicateurs"
